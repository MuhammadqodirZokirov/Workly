from aiogram import F, Router
from aiogram.types import CallbackQuery
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.application.matching import MatchingService
from workly.domain.errors import DomainError
from workly.infrastructure.db.models import User

from ..texts import lang_of, t

ERROR_TEXT = {"SLOTS_FILLED": "offer_slots_filled", "TIME_CONFLICT": "offer_time_conflict"}


async def offer_answer(call: CallbackQuery, db: AsyncSession, redis: Redis, notifier):
    """Taklifga botdagi Qabul/Rad — ilovadagi bilan bir xil servis (TZ 4-bo'lim)."""
    _, action, raw_id = call.data.split(":")
    user = await db.scalar(select(User).where(User.telegram_id == call.from_user.id))
    lang = user.lang if user else lang_of(call.from_user.language_code)
    if user is None:
        await call.answer(t("offer_gone", lang), show_alert=True)
        return
    svc = MatchingService(db, redis, notifier)
    try:
        if action == "a":
            offer = await svc.accept(user, int(raw_id))
        else:
            offer = await svc.decline(user, int(raw_id))
        await db.commit()
    except DomainError as e:
        await db.commit()  # muddati o'tgan/olib qo'yilgan holat saqlansin
        await call.answer(t(ERROR_TEXT.get(e.code, "offer_gone"), lang), show_alert=True)
        await call.message.edit_reply_markup(reply_markup=None)
        return

    done = "offer_accepted" if action == "a" else "offer_declined"
    await call.answer()
    await call.message.edit_text(f"{call.message.html_text}\n\n<b>{t(done, lang)}</b>", reply_markup=None)
    if action == "a":
        await notifier.worker_assigned(offer.id)


def create_router() -> Router:
    router = Router(name="offers")
    router.callback_query.register(offer_answer, F.data.regexp(r"^of:[ad]:\d+$"))
    return router
