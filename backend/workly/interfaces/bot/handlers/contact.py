from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from workly.application.users import UserService
from workly.domain.errors import Conflict
from workly.infrastructure.config import Settings

from ..texts import lang_of, t
from .keyboards import open_app_kb


async def got_contact(message: Message, db: AsyncSession, settings: Settings):
    tg, contact = message.from_user, message.contact
    lang = lang_of(tg.language_code)
    # Faqat o'z raqami: request_contact tugmasi orqali kelgan kontaktda user_id = yuboruvchi
    if contact.user_id != tg.id:
        await message.answer(t("phone_not_own", lang))
        return
    try:
        user = await UserService(db).link_telegram_phone(
            tg.id,
            contact.phone_number,
            full_name=tg.full_name,
            username=tg.username,
            language_code=tg.language_code,
        )
    except Conflict:
        await message.answer(t("phone_taken", lang), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(t("phone_ok", user.lang), reply_markup=ReplyKeyboardRemove())
    if kb := open_app_kb(user.lang, settings.webapp_url):
        await message.answer(t("open_app", user.lang), reply_markup=kb)


def create_router() -> Router:
    router = Router(name="contact")
    router.message.register(got_contact, F.contact)
    return router
