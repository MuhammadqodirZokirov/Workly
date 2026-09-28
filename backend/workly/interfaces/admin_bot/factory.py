from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workly.domain.users import Role, UserStatus
from workly.infrastructure.config import Settings
from workly.infrastructure.db.models import User

from ..bot.middlewares import DbSessionMiddleware
from .handlers import create_router

STAFF = {Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN}


class StaffMiddleware(BaseMiddleware):
    """Faqat bazada xodim roli bor va faol Telegram foydalanuvchi (TZ 16: "admin roli bor Telegram ID'lar")."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        db: AsyncSession = data["db"]
        user = await db.scalar(select(User).where(User.telegram_id == tg_user.id)) if tg_user is not None else None
        if user is None or user.status != UserStatus.ACTIVE or STAFF.isdisjoint(user.role_names):
            text = f"Ruxsat yo'q. Telegram ID: <code>{tg_user.id if tg_user else '?'}</code>"
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer("Ruxsat yo'q", show_alert=True)
            return None
        data["staff"] = user
        data["is_admin"] = bool({Role.ADMIN, Role.SUPER_ADMIN} & set(user.role_names))
        return await handler(event, data)


def create_admin_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.admin_bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )


def create_admin_dispatcher(maker: async_sessionmaker[AsyncSession], settings: Settings) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage(), settings=settings)
    dp.update.outer_middleware(DbSessionMiddleware(maker))
    staff = StaffMiddleware()
    dp.message.middleware(staff)
    dp.callback_query.middleware(staff)
    router = create_router()
    router.message.filter(F.chat.type == "private")
    dp.include_router(router)
    return dp


async def set_admin_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Menyu"),
            BotCommand(command="stats", description="Bugungi statistika"),
            BotCommand(command="cancel", description="Amalni bekor qilish"),
        ]
    )
