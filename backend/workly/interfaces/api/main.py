import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from workly.infrastructure.config import Settings, get_settings
from workly.infrastructure.crypto import DataCipher
from workly.infrastructure.db.session import make_engine, make_sessionmaker
from workly.infrastructure.sms import ConsoleSmsSender, EskizSmsSender, SmsSender
from workly.infrastructure.storage import EncryptedLocalStorage

from .errors import install_error_handlers
from .routers import (
    admin_catalog,
    admin_employers,
    admin_verification,
    auth,
    catalog,
    employer,
    files,
    matching,
    me,
    orders,
    webhooks,
    worker,
    workers_public,
)

log = logging.getLogger(__name__)

WEBHOOK_PATH = "/api/v1/webhooks/telegram"


def build_sms(settings: Settings) -> SmsSender:
    if settings.sms_provider == "eskiz":
        return EskizSmsSender(settings.eskiz_email, settings.eskiz_password.get_secret_value(), settings.eskiz_from)
    return ConsoleSmsSender()


def build_cipher(settings: Settings) -> DataCipher:
    return DataCipher(settings.data_encryption_key.get_secret_value(), settings.data_hash_key.get_secret_value())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Faza 1-lite: API, bot va (keyinroq) scheduler bitta jarayonda
    from workly.interfaces.bot.factory import create_bot, create_dispatcher, set_default_commands
    from workly.interfaces.bot.notifier import BotNotifier

    settings: Settings = app.state.settings
    engine = make_engine(settings.database_url)
    app.state.maker = make_sessionmaker(engine)
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.sms = build_sms(settings)
    app.state.cipher = build_cipher(settings)
    app.state.storage = EncryptedLocalStorage(settings.media_dir, app.state.cipher)

    polling_task = None
    bot = dp = None
    if settings.bot_mode != "off":
        bot = create_bot(settings)
        dp = create_dispatcher(app.state.maker, settings)
        app.state.bot, app.state.dp = bot, dp
        await set_default_commands(bot)
        if settings.bot_mode == "webhook":
            await bot.set_webhook(
                f"{settings.public_base_url.rstrip('/')}{WEBHOOK_PATH}",
                secret_token=settings.bot_webhook_secret.get_secret_value(),
                allowed_updates=dp.resolve_used_update_types(),
            )
        else:
            await bot.delete_webhook()
            polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    app.state.notifier = BotNotifier(bot, app.state.maker, app.state.sms, settings)
    if dp is not None:
        dp.workflow_data.update(redis=app.state.redis, notifier=app.state.notifier)
    stop = asyncio.Event()
    scheduler_task = None
    if settings.scheduler_enabled:
        from workly.workers.scheduler import run_forever

        scheduler_task = asyncio.create_task(run_forever(app.state.maker, app.state.redis, app.state.notifier, stop))

    try:
        yield
    finally:
        stop.set()
        if scheduler_task:
            await scheduler_task
        if polling_task:
            with contextlib.suppress(RuntimeError):
                await dp.stop_polling()
            with contextlib.suppress(asyncio.CancelledError):
                await polling_task
        if bot:
            await bot.session.close()
        await app.state.redis.aclose()
        await engine.dispose()


def create_app(settings: Settings | None = None, *, use_lifespan: bool = True) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Workly API",
        version="0.1.0",
        lifespan=lifespan if use_lifespan else None,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
        )
    install_error_handlers(app)

    api = APIRouter(prefix="/api/v1")
    routers = (
        auth,
        me,
        catalog,
        worker,
        workers_public,
        employer,
        orders,
        matching,
        admin_verification,
        admin_employers,
        admin_catalog,
        files,
        webhooks,
    )
    for module in routers:
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    return app
