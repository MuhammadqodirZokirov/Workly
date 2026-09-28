"""Domen xatolari. HTTP statuslarga moslash API qatlamida bajariladi."""

from typing import Any


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    message = "Xatolik"

    def __init__(self, message: str | None = None, *, code: str | None = None, details: Any = None):
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        super().__init__(self.message)


class ValidationFailed(DomainError):
    code = "VALIDATION_ERROR"
    message = "Ma'lumot noto'g'ri"


class NotFound(DomainError):
    code = "NOT_FOUND"
    message = "Topilmadi"


class Unauthorized(DomainError):
    code = "UNAUTHORIZED"
    message = "Avtorizatsiya talab qilinadi"


class Forbidden(DomainError):
    code = "FORBIDDEN"
    message = "Ruxsat yo'q"


class Conflict(DomainError):
    code = "CONFLICT"
    message = "Ziddiyat"


class InvalidState(DomainError):
    code = "INVALID_STATE"
    message = "Bu holatda amal bajarib bo'lmaydi"


class RateLimited(DomainError):
    code = "RATE_LIMITED"
    message = "Juda ko'p so'rov"
