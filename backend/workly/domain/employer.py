"""Ish beruvchi qoidalari (TZ 5-bo'lim)."""

from enum import StrEnum

from .errors import ValidationFailed


class EmployerType(StrEnum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"


class BusinessRejectReason(StrEnum):
    STIR_INVALID = "stir_invalid"  # STIR topilmadi yoki faol emas
    COMPANY_MISMATCH = "company_mismatch"  # nom STIR ga mos emas
    OTHER = "other"


class EmployerBadge(StrEnum):
    VERIFIED = "verified_employer"  # "Tasdiqlangan employer"


def normalize_stir(raw: str) -> str:
    """STIR (INN) — 9 raqam."""
    value = "".join(raw.split())
    if len(value) != 9 or not value.isdigit():
        raise ValidationFailed("STIR 9 ta raqamdan iborat bo'lishi kerak", code="INVALID_STIR")
    return value
