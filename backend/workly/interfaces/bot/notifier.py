import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workly.domain.orders import AssignmentStatus
from workly.infrastructure.config import Settings
from workly.infrastructure.db.models import Category, District, Offer, Order, Specialization, User, UserRole

from .texts import t

TASHKENT = ZoneInfo("Asia/Tashkent")


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def offer_keyboard(offer_id: int, lang: str, webapp_url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t("btn_accept", lang), callback_data=f"of:a:{offer_id}"),
            InlineKeyboardButton(text=t("btn_decline", lang), callback_data=f"of:d:{offer_id}"),
        ]
    ]
    if webapp_url and webapp_url.startswith("https://"):
        rows.append(
            [
                InlineKeyboardButton(
                    text=t("btn_details", lang), web_app=WebAppInfo(url=f"{webapp_url.rstrip('/')}/offers/{offer_id}")
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


log = logging.getLogger(__name__)


class BotNotifier:
    """Asosiy kanal — Telegram bot; bot bloklangan yoki Telegram yo'q bo'lsa — SMS (TZ 15-bo'lim)."""

    def __init__(
        self,
        bot: Bot | None,
        maker: async_sessionmaker[AsyncSession],
        sms,
        settings: Settings | None = None,
        admin_bot: Bot | None = None,
    ):
        self.bot, self.maker, self.sms, self.settings = bot, maker, sms, settings
        self.admin_bot = admin_bot  # signallar alohida admin botga (TZ 16); bo'lmasa — asosiy bot

    async def _staff_ids(self) -> set[int]:
        """Signal oluvchilar: sozlamadagi ADMINS + bazada xodim roli bor faol foydalanuvchilar."""
        ids = set(self.settings.admins if self.settings else [])
        async with self.maker() as db:
            rows = await db.scalars(
                select(User.telegram_id)
                .join(UserRole, UserRole.user_id == User.id)
                .where(
                    UserRole.role.in_(["moderator", "admin", "super_admin"]),
                    User.status == "active",
                    User.telegram_id.is_not(None),
                )
            )
            ids.update(rows)
        return ids

    async def _staff_signal(self, text: str) -> None:
        bot = self.admin_bot or self.bot
        if bot is None:
            return
        for tid in await self._staff_ids():
            try:
                await bot.send_message(tid, text)
            except TelegramAPIError as e:
                log.info("Admin signali yuborilmadi (%s): %s", tid, e)

    async def admin_signal(self, kind: str, object_id: int) -> None:
        """Navbat signallari: faqat havola — hujjat va selfie botga yuborilmaydi (TZ 19)."""
        base = (self.settings.webapp_url or "").rstrip("/") if self.settings else ""
        path = {"verification": "verifications", "business": "businesses"}.get(kind, "board")
        link = f"{base}/admin/{path}/{object_id}" if kind == "verification" else f"{base}/admin/{path}"
        await self._staff_signal(t(f"sig_{kind}", "uz_latn", object_id, link))

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

    # ---------- matching ----------
    async def _tg(self, telegram_id: int | None, text: str, **kw) -> int | None:
        if not (self.bot and telegram_id):
            return None
        try:
            msg = await self.bot.send_message(telegram_id, text, **kw)
            return msg.message_id
        except TelegramAPIError as e:
            log.info("Telegram xabari yuborilmadi (%s): %s", telegram_id, e)
            return None

    async def offer_new(self, offer_id: int) -> None:
        """Taklif: bot xabarida manzil va telefon yo'q — faqat tuman va ilovaga havola (TZ 15-bo'lim)."""
        async with self.maker() as db:
            offer = await db.get(Offer, offer_id)
            if offer is None or offer.status != "sent":
                return
            order: Order = offer.order
            worker = await db.get(User, offer.worker_id)
            cat = await db.get(Category, order.category_id)
            spec = await db.get(Specialization, order.specialization_id)
            district = await db.get(District, order.district_id)
            lang = worker.lang
            starts = order.starts_at if order.starts_at.tzinfo else order.starts_at.replace(tzinfo=UTC)
            if order.duration == "multi_day":
                duration = t("dur_multi_day", lang, order.days)
            elif order.duration:
                duration = t(f"dur_{order.duration}", lang)
            else:
                duration = t("dur_volume", lang)
            extras = "".join(
                t(f"offer_extras_{k}", lang)
                for k, on in (
                    ("night", order.is_night),
                    ("lunch", order.lunch),
                    ("transport", order.transport),
                    ("tools", order.tools_by == "worker"),
                )
                if on
            )
            expires = offer.expires_at if offer.expires_at.tzinfo else offer.expires_at.replace(tzinfo=UTC)
            minutes = max(1, round((expires - datetime.now(UTC)).total_seconds() / 60))
            text = t(
                "offer_new",
                lang,
                cat.name(lang),
                spec.name(lang),
                district.name(lang),
                f"{offer.distance_km:.1f}" if offer.distance_km is not None else "?",
                starts.astimezone(TASHKENT).strftime("%d.%m %H:%M"),
                duration,
                money(order.price["worker_net"]),
                extras,
                minutes,
            )
            webapp = self.settings.webapp_url if self.settings else None
            message_id = await self._tg(worker.telegram_id, text, reply_markup=offer_keyboard(offer.id, lang, webapp))
            if message_id:
                offer.telegram_message_id = message_id
                await db.commit()

    async def worker_assigned(self, offer_id: int) -> None:
        async with self.maker() as db:
            offer = await db.get(Offer, offer_id)
            if offer is None:
                return
            order = offer.order
            employer = await db.get(User, order.employer_id)
            filled = sum(1 for a in order.assignments if a.status == AssignmentStatus.ASSIGNED)
            await self._tg(
                employer.telegram_id,
                t("worker_assigned_employer", employer.lang, order.id, filled, order.workers_count),
            )

    async def worker_set_busy(self, user_id: int) -> None:
        async with self.maker() as db:
            user = await db.get(User, user_id)
        if user:
            await self._tg(user.telegram_id, t("worker_busy", user.lang))

    async def matching_exhausted(self, order_id: int) -> None:
        async with self.maker() as db:
            order = await db.get(Order, order_id)
            if order is None:
                return
            employer = await db.get(User, order.employer_id)
            filled = sum(1 for a in order.assignments if a.status == AssignmentStatus.ASSIGNED)
        await self._tg(employer.telegram_id, t("matching_exhausted_employer", employer.lang, order.id))
        await self._staff_signal(t("matching_exhausted_admin", "uz_latn", order.id, filled, order.workers_count))

    # ---------- ish kuni (TZ 10, 15) ----------
    # hodisa → kimga: w — ishchi, e — employer, a — adminlar
    WORKDAY_RECIPIENTS = {
        "remind_12h": "we",
        "remind_1h": "we",
        "remind_checkin": "w",
        "late_15": "we",
        "late_30": "ea",
        "no_show": "we",
        "worker_arrived": "e",
        "work_finished": "e",
        "confirm_reminder": "e",
        "confirmed": "we",
        "problem": "a",
        "order_cancelled": "w",
        "cancel_warning": "w",
        "dispute_resolved": "we",
    }

    async def workday_event(self, assignment_id: int, kind: str) -> None:
        from workly.infrastructure.db.models import Assignment

        async with self.maker() as db:
            a = await db.get(Assignment, assignment_id)
            if a is None:
                return
            await db.refresh(a, attribute_names=["order"])
            worker = await db.get(User, a.worker_id) if a.worker_id else None
            employer = await db.get(User, a.order.employer_id)
        who = self.WORKDAY_RECIPIENTS.get(kind, "")
        if "w" in who and worker:
            await self._tg(worker.telegram_id, t(f"wd_{kind}_worker", worker.lang, a.order.id))
        if "e" in who and employer:
            await self._tg(employer.telegram_id, t(f"wd_{kind}_employer", employer.lang, a.order.id))
        if "a" in who:
            await self._staff_signal(t(f"wd_{kind}_admin", "uz_latn", a.order.id, assignment_id))

    # ---------- buyurtma hodisalari (employerga) ----------
    async def order_event(self, order_id: int, kind: str) -> None:
        async with self.maker() as db:
            order = await db.get(Order, order_id)
            if order is None:
                return
            employer = await db.get(User, order.employer_id)
            filled = sum(1 for a in order.assignments if a.status == AssignmentStatus.ASSIGNED)
        await self._tg(employer.telegram_id, t(f"order_{kind}_employer", employer.lang, order.id, filled))
