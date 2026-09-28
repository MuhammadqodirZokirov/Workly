"""Narxlash, Faza 1: qat'iy narx + min/max (TZ 8-bo'lim). Pul — butun so'm, float ishlatilmaydi."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from .errors import ValidationFailed


class PriceUnit(StrEnum):
    DAY = "day"  # kun (8 soat); yarim kun = ×0.6
    HOUR = "hour"
    M2 = "m2"
    GUEST = "guest"  # mehmon soni


class Duration(StrEnum):
    HALF_DAY = "half_day"  # 4 soat
    DAY = "day"  # 8 soat
    MULTI_DAY = "multi_day"


HALF_DAY_FACTOR = Decimal("0.6")
SURCHARGE = Decimal("0.10")  # ishchi asbobi +10%, faqat Top ishchilar +10% — to'liq ishchiga
EMPLOYER_COMMISSION = Decimal("0.10")
WORKER_COMMISSION = Decimal("0.03")
MIN_FACTOR, MAX_FACTOR = Decimal("0.75"), Decimal("2")
MAX_DAYS = 30


def round_1000(value: Decimal) -> int:
    return int((value / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 1000)


def bound(base: int, factor: Decimal) -> int:
    return int((Decimal(base) * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def pct(value: int, rate: Decimal) -> int:
    return int((Decimal(value) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class PriceConfig:
    unit: PriceUnit
    base: int
    min_price: int
    max_price: int
    min_order_amount: int = 0

    @classmethod
    def from_base(cls, unit: PriceUnit, base: int, min_order_amount: int = 0) -> "PriceConfig":
        # Chegaralar TZ 8-jadvalidagidek aniq (150 000 → 112 500 / 300 000); yaxlitlash faqat narxga qo'llanadi
        return cls(unit, base, bound(base, MIN_FACTOR), bound(base, MAX_FACTOR), min_order_amount)


@dataclass(frozen=True)
class QuoteInput:
    workers: int
    duration: Duration | None = None  # kunlik birlikda
    days: int = 1
    volume: Decimal | None = None  # m², mehmon, soat
    worker_tools: bool = False
    top_only: bool = False


@dataclass(frozen=True)
class Quote:
    unit: PriceUnit
    worker_price: int  # bitta ishchiga bir kun uchun (hajm birligida — ishchi ulushi)
    days: int
    workers: int
    subtotal: int  # ishchilarga jami
    service_fee: int  # employer komissiyasi
    employer_total: int
    worker_net: int  # bitta ishchi bir kunda oladi ("Siz olasiz")
    platform_income: int
    commission_enabled: bool


def calculate(cfg: PriceConfig, q: QuoteInput, *, commission_enabled: bool) -> Quote:
    if not 1 <= q.workers <= 50:
        raise ValidationFailed("Ishchilar soni 1–50", code="INVALID_WORKERS")
    surcharge = 1 + (SURCHARGE if q.worker_tools else 0) + (SURCHARGE if q.top_only else 0)
    # Faza 1: narx = bazaviy; Faza 2 da P = B×K..., [min, max] oralig'ida
    unit_price = Decimal(min(max(cfg.base, cfg.min_price), cfg.max_price))

    if cfg.unit == PriceUnit.DAY:
        if q.duration is None:
            raise ValidationFailed("Davomiylikni tanlang", code="DURATION_REQUIRED")
        days = q.days if q.duration == Duration.MULTI_DAY else 1
        if q.duration == Duration.MULTI_DAY and not 2 <= days <= MAX_DAYS:
            raise ValidationFailed(f"Bir necha kun: 2–{MAX_DAYS}", code="INVALID_DAYS")
        factor = HALF_DAY_FACTOR if q.duration == Duration.HALF_DAY else Decimal(1)
        worker_price = round_1000(unit_price * factor * surcharge)
    else:
        # Uy xizmatlari: birlik narxi × hajm, eng kam summa bilan; ishchilar orasida teng bo'linadi
        if q.volume is None or q.volume <= 0:
            raise ValidationFailed("Ish hajmini kiriting", code="VOLUME_REQUIRED")
        days = 1
        total = max(unit_price * q.volume * surcharge, Decimal(cfg.min_order_amount))
        worker_price = round_1000(total / q.workers)

    subtotal = worker_price * q.workers * days
    fee = pct(subtotal, EMPLOYER_COMMISSION) if commission_enabled else 0
    worker_fee = pct(worker_price, WORKER_COMMISSION) if commission_enabled else 0
    worker_net = worker_price - worker_fee
    return Quote(
        unit=cfg.unit,
        worker_price=worker_price,
        days=days,
        workers=q.workers,
        subtotal=subtotal,
        service_fee=fee,
        employer_total=subtotal + fee,
        worker_net=worker_net,
        platform_income=fee + worker_fee * q.workers * days,
        commission_enabled=commission_enabled,
    )
