from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rabotago.domain.users import Lang
from rabotago.infrastructure.config import Settings

from .handlers import setup_routers
from .middlewares import DbSessionMiddleware, ThrottlingMiddleware
from .texts import t


def create_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(maker: async_sessionmaker[AsyncSession], settings: Settings) -> Dispatcher:
    # TODO: bir nechta jarayonga o'tganda FSM uchun RedisStorage
    dp = Dispatcher(storage=MemoryStorage(), settings=settings)
    dp.update.outer_middleware(DbSessionMiddleware(maker))
    dp.message.middleware(ThrottlingMiddleware())
    dp.include_router(setup_routers())
    return dp


async def set_default_commands(bot: Bot) -> None:
    for lang, code in ((Lang.UZ_LATN, None), (Lang.RU, "ru")):
        await bot.set_my_commands(
            [
                BotCommand(command="start", description=t("cmd_start", lang)),
                BotCommand(command="help", description=t("cmd_help", lang)),
            ],
            language_code=code,
        )
