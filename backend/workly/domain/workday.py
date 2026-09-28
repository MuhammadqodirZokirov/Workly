"""Ish kuni: check-in, kechikish, yakunlash, intizom va reyting (TZ 10, 11, 13-bo'limlar). Sof funksiyalar."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from .errors import InvalidState, ValidationFailed

# ---------- check-in (TZ 10) ----------
CHECKIN_OPENS = timedelta(minutes=30)  # T−30 dan
CHECKIN_CLOSES = timedelta(minutes=60)  # T+60 gacha
MAX_DISTANCE_M = 200
MAX_ACCURACY_M = 100
EMPLOYER_CONFIRM_WAIT = timedelta(minutes=15)  # javob bo'lmasa GPS va selfie yetarli

# ---------- kechikish ----------
LATE_REMIND = timedelta(minutes=15)  # T+15: ishchiga eslatma, employerga "kechikmoqda"
LATE_ESCALATE = timedelta(minutes=30)  # T+30: moderatorga qo'ng'iroq vazifasi, employerga tanlov
NO_SHOW_AFTER = timedelta(minutes=60)  # T+60: "Kelmadi" + tezkor almashtirish
REMINDERS = {
    "remind_12h": timedelta(hours=12),
    "remind_1h": timedelta(hours=1),
    "remind_checkin": timedelta(minutes=15),
}

# ---------- yakunlash ----------
AUTO_CONFIRM_AFTER = timedelta(hours=24)
CONFIRM_REMINDER_AFTER = timedelta(hours=20)
REVIEW_WINDOW = timedelta(hours=48)

# ---------- intizom (TZ 11): Faza 1-lite — pulsiz jazolar, faqat Ishonchlilik ----------
RELIABILITY_START = 100
RELIABILITY_CLEAN_JOB = 2
RELIABILITY_SUSPEND_BELOW = 40
LATE_PENALTY = -3  # kechikish 15–60 daqiqa


class NoShowAction(StrEnum):
    WARN = "warn"
    SUSPEND_3D = "suspend_3d"
    BLOCK = "block"


def no_show_penalty(count_90d_including_this: int) -> tuple[int, NoShowAction]:
    """1-marta −20 + ogohlantirish; 2-marta −30 + 3 kun to'xtatish; 3-marta −40 + blok."""
    if count_90d_including_this <= 1:
        return -20, NoShowAction.WARN
    if count_90d_including_this == 2:
        return -30, NoShowAction.SUSPEND_3D
    return -40, NoShowAction.BLOCK


def clamp_reliability(value: int) -> int:
    return max(0, min(RELIABILITY_START, value))


def ensure_checkin_window(starts_at: datetime, now: datetime) -> None:
    if now < starts_at - CHECKIN_OPENS:
        raise InvalidState("Check-in ish boshlanishidan 30 daqiqa oldin ochiladi", code="CHECKIN_TOO_EARLY")
    if now > starts_at + CHECKIN_CLOSES:
        raise InvalidState("Check-in vaqti o'tib ketgan", code="CHECKIN_CLOSED")


def check_gps(distance_m: float, accuracy_m: float) -> None:
    if accuracy_m > MAX_ACCURACY_M:
        raise ValidationFailed(
            "GPS aniqligi past — ochiq joyda qayta urinib ko'ring",
            code="GPS_INACCURATE",
            details={"accuracy_m": round(accuracy_m)},
        )
    if distance_m > MAX_DISTANCE_M:
        raise ValidationFailed("Ish joyidan uzoqdasiz", code="GPS_TOO_FAR", details={"distance_m": round(distance_m)})


# ---------- reyting (TZ 13) ----------
PRIOR_MEAN = 4.5
PRIOR_WEIGHT = 3
LAST_N = 20
NEW_BADGE_REVIEWS = 3


@dataclass(frozen=True)
class RatingInput:
    rating: float
    is_auto: bool


def bayes_rating(reviews_newest_first: list[RatingInput]) -> float | None:
    """R = (C·m + Σ wᵢrᵢ) / (C + Σ wᵢ), m = 4.5, C = 3, oxirgi 20 ta; vazn eng yangisi 1.0 → 20-chisi 0.5."""
    items = reviews_newest_first[:LAST_N]
    if not items:
        return None
    weights = [1.0 - 0.5 * i / (LAST_N - 1) for i in range(len(items))]
    num = PRIOR_WEIGHT * PRIOR_MEAN + sum(w * r.rating for w, r in zip(weights, items, strict=True))
    return round(num / (PRIOR_WEIGHT + sum(weights)), 2)


def counted_reviews(reviews: list[RatingInput]) -> int:
    """Avtomatik baholar soni chegaralariga ("Yangi", ≥ 5 baho) kirmaydi."""
    return sum(1 for r in reviews if not r.is_auto)


class WorkerTag(StrEnum):
    """Employer ishchiga qo'yadi"""

    ON_TIME = "on_time"
    QUALITY = "quality"
    POLITE = "polite"


class EmployerTag(StrEnum):
    """Ishchi employerga qo'yadi"""

    PAID_ON_TIME = "paid_on_time"
    POLITE = "polite"
    CLEAR_TASK = "clear_task"
