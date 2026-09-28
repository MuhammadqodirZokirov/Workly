"""Bekor qilish qoidalari (TZ 11-bo'lim).

Faza 1-lite: pul jarimasi olinmaydi (TZ 22 — "pulsiz jazolar"), lekin summa ekranda
ko'rsatiladi va jurnalga yoziladi — Faza 1 to'liqda balans/qarz orqali olinadi.
Intizom Ishonchlilik indeksi orqali ishlaydi.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

PENALTIES_CHARGED = False  # Faza 1 to'liqda True — xizmat balansi va qarz (TZ 9)

FREE_BEFORE = timedelta(hours=24)
LATE_BEFORE = timedelta(hours=6)
PARTIAL_DECISION_BEFORE = timedelta(minutes=60)  # T−60: qisman to'lgan buyurtma (OS-10)
WORKER_MONTHLY_CANCEL_WARN = 3  # oyiga 3+ bepul bekor — ogohlantirish


class CancelTier(StrEnum):
    FREE = "free"  # ishchi tayinlanmagan yoki ≥ 24 soat
    H6_24 = "h6_24"
    LT6 = "lt6"
    AFTER_ARRIVAL = "after_arrival"


@dataclass(frozen=True)
class CancelTerms:
    tier: CancelTier
    percent: int  # jarima foizi
    amount: int  # so'm (pilotda olinmaydi)
    reliability: int  # indeks o'zgarishi
    charged: bool = PENALTIES_CHARGED


def tier_for(starts_at: datetime, now: datetime) -> CancelTier:
    left = starts_at - now
    if left >= FREE_BEFORE:
        return CancelTier.FREE
    if left >= LATE_BEFORE:
        return CancelTier.H6_24
    return CancelTier.LT6


# Employer: foiz — buyurtma summasidan (yetib kelgandan keyin — birinchi kun). Ishonchlilik
# qiymatlari TZ da ko'rsatilmagan ("bekor qilishlar kamaytiradi") — ishchi jadvaliga o'xshash qilib olindi.
_EMPLOYER = {
    CancelTier.FREE: (0, 0),
    CancelTier.H6_24: (20, -5),
    CancelTier.LT6: (50, -10),
    CancelTier.AFTER_ARRIVAL: (100, -10),
}

# Ishchi: foiz — shu tayinlovdagi kunlik narxdan
_WORKER = {
    CancelTier.FREE: (0, 0),
    CancelTier.H6_24: (0, -5),
    CancelTier.LT6: (20, -10),
}


def employer_terms(
    starts_at: datetime,
    now: datetime,
    *,
    has_workers: bool,
    arrived: bool,
    order_total: int,
    first_day_total: int,
) -> CancelTerms:
    if not has_workers:
        return CancelTerms(CancelTier.FREE, 0, 0, 0)
    tier = CancelTier.AFTER_ARRIVAL if arrived else tier_for(starts_at, now)
    percent, reliability = _EMPLOYER[tier]
    base = first_day_total if tier == CancelTier.AFTER_ARRIVAL else order_total
    return CancelTerms(tier, percent, round_sum(base * percent / 100), reliability)


def worker_terms(starts_at: datetime, now: datetime, daily_price: int) -> CancelTerms:
    tier = tier_for(starts_at, now)
    percent, reliability = _WORKER[tier]
    return CancelTerms(tier, percent, round_sum(daily_price * percent / 100), reliability)


def round_sum(value: float) -> int:
    """1 000 so'mgacha yaxlitlash (TZ 9)."""
    return int(round(value / 1000) * 1000)


def needs_partial_decision(starts_at: datetime, now: datetime) -> bool:
    return starts_at - PARTIAL_DECISION_BEFORE <= now < starts_at


def shrink_price(price: dict, workers: int) -> dict:
    """Topilganlar bilan boshlash: narx topilgan ishchilar soniga qayta hisoblanadi, asl nusxa saqlanadi."""
    original = price.get("original") or {k: v for k, v in price.items() if k != "original"}
    old = original["workers"]
    ratio = workers / old if old else 0
    out = dict(original)
    out["workers"] = workers
    for key in ("subtotal", "service_fee", "employer_total"):
        if key in out:
            out[key] = int(round(original[key] * ratio))
    out["original"] = original
    return out
