from enum import StrEnum


class Role(StrEnum):
    WORKER = "worker"
    EMPLOYER = "employer"
    AGENT = "agent"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


# Foydalanuvchi o'ziga o'zi qo'sha oladigan rollar; qolganlarini faqat super admin beradi
SELF_ASSIGNABLE_ROLES = frozenset({Role.WORKER, Role.EMPLOYER})


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class Lang(StrEnum):
    UZ_LATN = "uz_latn"
    UZ_CYRL = "uz_cyrl"
    RU = "ru"

    @classmethod
    def from_telegram(cls, language_code: str | None) -> "Lang":
        return cls.RU if language_code == "ru" else cls.UZ_LATN


class ConsentDoc(StrEnum):
    TERMS = "terms"
    PRIVACY = "privacy"
    WORKER_CONTRACT = "worker_contract"
    EMPLOYER_CONTRACT = "employer_contract"
