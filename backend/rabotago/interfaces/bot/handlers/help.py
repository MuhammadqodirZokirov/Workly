from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..texts import lang_of, t


async def bot_help(message: Message):
    await message.answer(t("help", lang_of(message.from_user.language_code), "/start", "/help"))


def create_router() -> Router:
    router = Router(name="help")
    router.message.register(bot_help, Command("help"))
    return router
