"""Ishchi moduli qoidalari (TZ 4-bo'lim)."""

from datetime import date
from enum import StrEnum

from .errors import InvalidState, ValidationFailed

MIN_AGE = 18


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class Experience(StrEnum):
    NONE = "none"
    Y1_2 = "1_2"
    Y3_5 = "3_5"
    Y5_PLUS = "5_plus"


class DocType(StrEnum):
    """Shaxsni tasdiqlovchi hujjat turi."""

    ID_CARD = "id_card"
    PASSPORT = "passport"


class FileKind(StrEnum):
    ID_CARD_FRONT = "id_card_front"
    ID_CARD_BACK = "id_card_back"
    PASSPORT_MAIN = "passport_main"
    SELFIE = "selfie"
    QUALIFICATION = "qualification"  # elektrik/santexnik guvohnomasi — "Tasdiqlangan malaka"
    CRIMINAL_RECORD = "criminal_record"  # sudlanmaganlik ma'lumotnomasi — "Tekshirilgan"
    AVATAR = "avatar"  # ommaviy profil rasmi (selfie emas — u maxfiy)


REQUIRED_FILES = {
    DocType.ID_CARD: {FileKind.ID_CARD_FRONT, FileKind.ID_CARD_BACK, FileKind.SELFIE},
    DocType.PASSPORT: {FileKind.PASSPORT_MAIN, FileKind.SELFIE},
}


class VerificationStatus(StrEnum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


_TRANSITIONS = {
    VerificationStatus.NOT_SUBMITTED: {VerificationStatus.PENDING},
    VerificationStatus.PENDING: {VerificationStatus.VERIFIED, VerificationStatus.REJECTED},
    VerificationStatus.REJECTED: {VerificationStatus.PENDING},
    VerificationStatus.VERIFIED: {VerificationStatus.EXPIRED},
    VerificationStatus.EXPIRED: {VerificationStatus.PENDING},
}


def ensure_transition(current: str, target: VerificationStatus) -> None:
    if target not in _TRANSITIONS.get(VerificationStatus(current), set()):
        raise InvalidState(f"Verifikatsiya holati {current} → {target} o'tishi mumkin emas")


class RejectReason(StrEnum):
    """Rad sabablari shablonlari (TZ 4-bo'lim)."""

    BLURRY = "blurry"  # rasm noaniq
    MISMATCH = "mismatch"  # ma'lumot mos emas
    UNDERAGE = "underage"  # yosh yetmaydi
    DOC_EXPIRED = "doc_expired"  # hujjat muddati o'tgan
    DUPLICATE = "duplicate"  # takroriy akkaunt
    OTHER = "other"


class Badge(StrEnum):
    QUALIFIED = "qualified"  # Tasdiqlangan malaka
    BACKGROUND_CHECKED = "background_checked"  # Tekshirilgan (sudlanmaganlik)


# 3 ta bahogacha profilda "Yangi" belgisi (TZ 13-bo'lim)
NEW_BADGE_MAX_REVIEWS = 3


def age_on(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def ensure_adult(birth_date: date, today: date) -> None:
    if birth_date > today or age_on(birth_date, today) > 100:
        raise ValidationFailed("Tug'ilgan sana noto'g'ri", code="INVALID_BIRTH_DATE")
    if age_on(birth_date, today) < MIN_AGE:
        raise ValidationFailed("Ishchi 18 yoshdan katta bo'lishi kerak", code="UNDERAGE")


def normalize_doc_number(raw: str) -> str:
    """AA 1234567 / aa1234567 → AA1234567 (ID karta va pasport: 2 harf + 7 raqam)."""
    value = "".join(raw.split()).upper()
    if len(value) != 9 or not value[:2].isalpha() or not value[:2].isascii() or not value[2:].isdigit():
        raise ValidationFailed("Hujjat raqami AA1234567 formatida bo'lishi kerak", code="INVALID_DOC_NUMBER")
    return value
