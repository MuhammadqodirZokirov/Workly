from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from ..texts import t


def share_phone_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("share_phone_btn", lang), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def open_app_kb(lang: str, webapp_url: str) -> InlineKeyboardMarkup | None:
    # Telegram Mini App faqat https manzil bilan ishlaydi
    if not webapp_url.startswith("https://"):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("open_app_btn", lang), web_app=WebAppInfo(url=webapp_url)),
            ]
        ]
    )
