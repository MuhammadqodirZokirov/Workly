"""Buyurtma hayot sikli va yaratish qoidalari (TZ 5, 6-bo'limlar)."""

import re
from datetime import datetime, time, timedelta
from enum import StrEnum

from .errors import InvalidState, ValidationFailed

MAX_WORKERS = 50
FIRST_ORDER_MAX_WORKERS = 3
NEW_EMPLOYER_APPROVAL_FROM = 10  # yangi employerda 10+ ishchi — admin tasdig'i
MAX_DAYS_AHEAD = 30
MIN_LEAD = timedelta(minutes=30)
NIGHT_START, NIGHT_END = time(22, 0), time(6, 0)
QUOTE_TTL_SECONDS = 15 * 60  # narx 15 daqiqa bloklanadi


class OrderStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    MATCHING = "matching"
    PARTIALLY_ASSIGNED = "partially_assigned"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


ACTIVE_STATUSES = {
    OrderStatus.PENDING_APPROVAL,
    OrderStatus.MATCHING,
    OrderStatus.PARTIALLY_ASSIGNED,
    OrderStatus.ASSIGNED,
    OrderStatus.IN_PROGRESS,
}

_TRANSITIONS = {
    OrderStatus.PENDING_APPROVAL: {OrderStatus.MATCHING, OrderStatus.CANCELLED},
    OrderStatus.MATCHING: {
        OrderStatus.PARTIALLY_ASSIGNED,
        OrderStatus.ASSIGNED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PARTIALLY_ASSIGNED: {
        OrderStatus.MATCHING,
        OrderStatus.ASSIGNED,
        OrderStatus.IN_PROGRESS,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.ASSIGNED: {OrderStatus.PARTIALLY_ASSIGNED, OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED},
    OrderStatus.IN_PROGRESS: {OrderStatus.COMPLETED},
}


def ensure_order_transition(current: str, target: OrderStatus) -> None:
    if target not in _TRANSITIONS.get(OrderStatus(current), set()):
        raise InvalidState(f"Buyurtma holati {current} → {target} o'tishi mumkin emas")


class AssignmentStatus(StrEnum):
    OPEN = "open"  # ishchi izlanmoqda
    ASSIGNED = "assigned"
    ARRIVED = "arrived"
    WORKING = "working"
    FINISHED = "finished"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    REPLACED = "replaced"


class ToolsBy(StrEnum):
    EMPLOYER = "employer"
    WORKER = "worker"  # +10%


class PaymentMode(StrEnum):
    CASH = "cash"
    ONLINE = "online"  # Faza 2


def is_night(start: time) -> bool:
    return start >= NIGHT_START or start < NIGHT_END


def validate_start(starts_at: datetime, now: datetime) -> None:
    if starts_at < now + MIN_LEAD:
        raise ValidationFailed("Boshlanish vaqti kamida 30 daqiqadan keyin bo'lsin", code="START_TOO_SOON")
    if starts_at.date() > (now + timedelta(days=MAX_DAYS_AHEAD)).date():
        raise ValidationFailed(f"Buyurtma {MAX_DAYS_AHEAD} kungacha oldindan beriladi", code="START_TOO_FAR")


# Taqiqlangan ishlar (TZ 14-bo'lim) — oddiy so'z filtri; yakuniy qaror moderatsiyada
_PROHIBITED = [
    r"qarz\s*undir",
    r"kollektor",
    r"коллектор",
    r"qo['ʻ’]?riqchi",
    r"охран",
    r"intim",
    r"интим",
    r"eskort",
    r"эскорт",
    r"massaj\s*salon",
    r"portlov",
    r"взрывч",
    r"hujjat(ingiz)?ni\s*qoldir",
    r"pasport(ingiz)?ni\s*qoldir",
    r"залог",
]
_PROHIBITED_RE = re.compile("|".join(_PROHIBITED), re.IGNORECASE)


def check_description(text: str | None) -> None:
    if text and (m := _PROHIBITED_RE.search(text)):
        raise ValidationFailed(
            "Tavsifda taqiqlangan ish turi aniqlandi", code="PROHIBITED_CONTENT", details={"match": m.group(0)}
        )


class OfferStatus(StrEnum):
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


MATCHING_STATUSES = {OrderStatus.MATCHING, OrderStatus.PARTIALLY_ASSIGNED}
BUSY_ASSIGNMENT_STATUSES = {"assigned", "arrived", "working"}


def derive_status(open_slots: int, filled_slots: int) -> OrderStatus:
    """Buyurtma holati tayinlovlardan hisoblanadi (TZ 6-bo'lim)."""
    if open_slots == 0 and filled_slots > 0:
        return OrderStatus.ASSIGNED
    return OrderStatus.PARTIALLY_ASSIGNED if filled_slots else OrderStatus.MATCHING
