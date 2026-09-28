import re

from .errors import ValidationFailed


def normalize_phone(raw: str) -> str:
    """O'zbekiston raqamini +998XXXXXXXXX ko'rinishiga keltiradi."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        raise ValidationFailed("Telefon raqam +998XXXXXXXXX formatida bo'lishi kerak", code="INVALID_PHONE")
    return "+" + digits
