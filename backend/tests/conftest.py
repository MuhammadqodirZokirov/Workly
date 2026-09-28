import os

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from workly.infrastructure.config import Settings
from workly.infrastructure.db import models  # noqa: F401
from workly.infrastructure.db.base import Base
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


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        jwt_secret="test-secret-test-secret-test-secret",
        bot_token=BOT_TOKEN,
        bot_mode="off",
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
