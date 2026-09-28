import os
import time

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from workly.infrastructure.config import Settings
from workly.infrastructure.db import models  # noqa: F401
from workly.infrastructure.db.base import Base
from workly.infrastructure.db.models import UserRole
from workly.infrastructure.db.session import make_sessionmaker
from workly.infrastructure.seed import seed
from workly.infrastructure.storage import EncryptedLocalStorage
from workly.interfaces.api.main import build_cipher, create_app

BOT_TOKEN = "123456:TEST-token"

# TEST_DATABASE_URL berilsa (masalan CI'dagi PostgreSQL) — o'sha ishlatiladi, aks holda SQLite xotirada
DB_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite://")


class FakeSms:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone: str, text: str) -> None:
        self.sent.append((phone, text))

    def last_code(self) -> str:
        return self.sent[-1][1].rsplit(" ", 1)[-1]


FERNET_KEY = "7kS8GqkH1xBzuxwWm0bTtBvVh3gJ2pQ1l0kQyE4H0rM="


class FakeNotifier:
    def __init__(self):
        self.calls: list[tuple] = []

    async def verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        self.calls.append((user_id, approved, reason))

    async def business_verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        self.calls.append(("business", user_id, approved, reason))

    async def offer_new(self, offer_id: int) -> None:
        self.calls.append(("offer_new", offer_id))

    async def worker_assigned(self, offer_id: int) -> None:
        self.calls.append(("worker_assigned", offer_id))

    async def worker_set_busy(self, user_id: int) -> None:
        self.calls.append(("worker_set_busy", user_id))

    async def matching_exhausted(self, order_id: int) -> None:
        self.calls.append(("matching_exhausted", order_id))


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        jwt_secret="test-secret-test-secret-test-secret",
        bot_token=BOT_TOKEN,
        bot_mode="off",
        scheduler_enabled=False,
        database_url=DB_URL,
        auth_rate_limit_per_min=1000,
        data_encryption_key=FERNET_KEY,
        data_hash_key="test-hash-key",
        media_dir=str(tmp_path / "media"),
    )


@pytest.fixture
async def engine():
    kwargs = {"poolclass": StaticPool} if DB_URL.startswith("sqlite") else {}
    engine = create_async_engine(DB_URL, **kwargs)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def maker(engine):
    maker = make_sessionmaker(engine)
    async with maker() as s:
        await seed(s)
        await s.commit()
    return maker


@pytest.fixture
async def db(maker):
    async with maker() as s:
        yield s


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis()


@pytest.fixture
def sms() -> FakeSms:
    return FakeSms()


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def app(settings, maker, redis, sms, notifier):
    app = create_app(settings, use_lifespan=False)
    app.state.maker, app.state.redis, app.state.sms = maker, redis, sms
    app.state.cipher = build_cipher(settings)
    app.state.storage = EncryptedLocalStorage(settings.media_dir, app.state.cipher)
    app.state.notifier = notifier
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def login(client, sms):
    """SMS orqali kirib, (tokenlar, headers) qaytaradi."""

    async def _login(phone: str = "+998901234567"):
        await client.post("/api/v1/auth/otp/send", json={"phone": phone})
        r = await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": sms.last_code()})
        assert r.status_code == 200, r.text
        body = r.json()
        return body, {"Authorization": f"Bearer {body['access_token']}"}

    return _login


# ---------------- umumiy ishchi/moderator fixture'lari ----------------
@pytest.fixture
async def catalog(client):
    cats = {c["code"]: c for c in (await client.get("/api/v1/catalog/categories")).json()}
    districts = (await client.get("/api/v1/catalog/districts")).json()
    return cats, districts


@pytest.fixture
async def worker(client, login, redis):
    """Ishchi rolidagi, roziliklari berilgan foydalanuvchi."""

    async def _make(phone="+998901234567"):
        await redis.delete(f"otp:cooldown:{phone}")
        body, h = await login(phone)
        await client.post("/api/v1/me/roles", json={"role": "worker"}, headers=h)
        await client.post(
            "/api/v1/me/consents",
            headers=h,
            json={"items": [{"doc_type": d, "version": "1.0"} for d in ("terms", "privacy", "worker_contract")]},
        )
        return body["user"]["id"], h

    return _make


def full_profile(cats, districts):
    c = cats["construction"]
    return {
        "last_name": "Toshmatov",
        "first_name": "Jasur ",
        "middle_name": "Alisher o'g'li",
        "birth_date": "1995-05-10",
        "gender": "male",
        "district_ids": [districts[0]["id"], districts[1]["id"]],
        "home_point": {"lat": 41.31, "lon": 69.24},
        "skills": [
            {
                "category_id": c["id"],
                "experience": "3_5",
                "specialization_ids": [c["specializations"][0]["id"], c["specializations"][5]["id"]],
            }
        ],
        "emergency_contact": {"name": "Ota", "phone": "+998907654321"},
    }


async def complete_worker(client, h, cats, districts):
    from .test_worker import JPEG

    assert (
        await client.put("/api/v1/worker/profile", json=full_profile(cats, districts), headers=h)
    ).status_code == 200
    for kind in ("id_card_front", "id_card_back", "selfie"):
        r = await client.post(
            "/api/v1/worker/files", headers=h, data={"kind": kind}, files={"file": ("a.jpg", JPEG, "image/jpeg")}
        )
        assert r.status_code == 201, r.text


@pytest.fixture
async def moderator(client, login, redis, db, elevate):
    await redis.delete("otp:cooldown:+998909999999")
    body, h = await login("+998909999999")
    db.add(UserRole(user_id=body["user"]["id"], role="moderator"))
    await db.commit()
    return body["user"]["id"], await elevate(body["user"]["id"], h)


@pytest.fixture
def elevate(client, db, app, redis):
    """Xodim uchun TOTP sozlab, admin panel (mfa) tokenini qaytaradi."""
    from workly.application.admin_auth import AdminAuthService
    from workly.domain.totp import code_at
    from workly.infrastructure.db.models import User

    async def _elevate(user_id: int, headers: dict) -> dict:
        user = await db.get(User, user_id)
        await db.refresh(user)
        svc = AdminAuthService(db, redis, app.state.settings, app.state.cipher)
        uri = await svc.setup(user)
        await db.commit()
        secret = uri.split("secret=")[1].split("&")[0]
        code = code_at(secret, int(time.time() // 30))
        r = await client.post("/api/v1/admin/auth/totp", json={"code": code}, headers=headers)
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _elevate
