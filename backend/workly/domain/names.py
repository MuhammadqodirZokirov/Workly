from .errors import ValidationFailed


def clean_name(value: str, field: str) -> str:
    name = " ".join(value.split())
    if len(name) < 2 or not all(ch.isalpha() or ch in " -'ʻʼ’" for ch in name):
        raise ValidationFailed("Ism faqat harflardan iborat bo'lsin", code="INVALID_NAME", details=[field])
    return name


def document_full_name(last: str, first: str, middle: str | None) -> str:
    """Hujjatdagi tartib: Familiya Ism Otasining ismi."""
    return " ".join(p for p in (last, first, middle) if p)


def public_name(first: str | None, last: str | None) -> str | None:
    """Ommaviy profil: "Jasur T." (TZ 4-bo'lim)."""
    if not first:
        return None
    return f"{first} {last[0]}." if last else first
