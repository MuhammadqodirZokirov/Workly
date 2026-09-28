import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workly.infrastructure.db.models import User
from workly.infrastructure.sms import SmsSender

from .texts import t

log = logging.getLogger(__name__)


class BotNotifier:
    """Asosiy kanal — Telegram bot; bot bloklangan yoki Telegram yo'q bo'lsa — SMS (TZ 15-bo'lim)."""

    def __init__(self, bot: Bot | None, maker: async_sessionmaker[AsyncSession], sms: SmsSender):
        self.bot, self.maker, self.sms = bot, maker, sms

    async def _send(self, user_id: int, key: str, *arg_keys: str) -> None:
        async with self.maker() as db:
            user = await db.get(User, user_id)
        if user is None:
            return
        text = t(key, user.lang, *(t(k, user.lang) for k in arg_keys))
        if self.bot and user.telegram_id:
            try:
                await self.bot.send_message(user.telegram_id, text)
                return
            except TelegramForbiddenError:
                log.info("Bot bloklangan (user_id=%s), SMS ga o'tamiz", user_id)
            except TelegramAPIError as e:
                log.warning("Bot xabari yuborilmadi (user_id=%s): %s", user_id, e)
        if user.phone:
            await self.sms.send(user.phone, f"Workly: {text}")

    async def verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        if approved:
            await self._send(user_id, "verification_approved")
        else:
            await self._send(user_id, "verification_rejected", f"reason_{reason}")

    async def business_verification_result(self, user_id: int, approved: bool, reason: str | None) -> None:
        if approved:
            await self._send(user_id, "business_approved")
        else:
            await self._send(user_id, "business_rejected", f"business_reason_{reason}")
