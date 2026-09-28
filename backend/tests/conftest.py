import os

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from rabotago.infrastructure.config import Settings
from rabotago.infrastructure.db import models  # noqa: F401
from rabotago.infrastructure.db.base import Base
from rabotago.infrastructure.db.session import make_sessionmaker
from rabotago.infrastructure.seed import seed
from rabotago.interfaces.api.main import create_app

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


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        jwt_secret="test-secret-test-secret-test-secret",
        bot_token=BOT_TOKEN,
        bot_mode="off",
        database_url=DB_URL,
        auth_rate_limit_per_min=1000,
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
def app(settings, maker, redis, sms):
    app = create_app(settings, use_lifespan=False)
    app.state.maker, app.state.redis, app.state.sms = maker, redis, sms
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
