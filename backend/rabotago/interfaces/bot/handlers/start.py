from aiogram import Router, html
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rabotago.infrastructure.config import Settings
from rabotago.infrastructure.db.models import User

from ..texts import lang_of, t
from .keyboards import open_app_kb, share_phone_kb


async def bot_start(message: Message, db: AsyncSession, settings: Settings):
    tg = message.from_user
    user = await db.scalar(select(User).where(User.telegram_id == tg.id))
    lang = user.lang if user else lang_of(tg.language_code)

    await message.answer(t("start", lang, html.quote(tg.full_name)))
    if user is None or user.phone is None:
        await message.answer(t("share_phone_ask", lang), reply_markup=share_phone_kb(lang))
    elif kb := open_app_kb(lang, settings.webapp_url):
        await message.answer(t("open_app", lang), reply_markup=kb)


def create_router() -> Router:
    router = Router(name="start")
    router.message.register(bot_start, CommandStart())
    return router
