from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from rabotago.domain.errors import Conflict, Forbidden
from rabotago.domain.phone import normalize_phone
from rabotago.domain.users import SELF_ASSIGNABLE_ROLES, ConsentDoc, Lang, Role, UserStatus
from rabotago.infrastructure.db.models import AuthSession, Consent, User, UserRole


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_profile(self, user: User, *, full_name: str | None = None, lang: Lang | None = None) -> User:
        if full_name is not None:
            user.full_name = full_name.strip() or None
        if lang is not None:
            user.lang = lang
        await self.db.flush()
        return user

    async def add_role(self, user: User, role: Role) -> User:
        if role not in SELF_ASSIGNABLE_ROLES:
            raise Forbidden("Bu rolni faqat super admin beradi", code="ROLE_NOT_ALLOWED")
        if role not in user.role_names:
            user.roles.append(UserRole(role=role))
            await self.db.flush()
        return user

    async def accept_consents(
        self, user: User, docs: list[tuple[ConsentDoc, str]], ip: str | None, user_agent: str | None
    ) -> None:
        for doc, version in docs:
            self.db.add(
                Consent(
                    user_id=user.id, doc_type=doc, version=version, ip=ip, user_agent=(user_agent or "")[:300] or None
                )
            )
        await self.db.flush()

    async def delete_account(self, user: User) -> None:
        # TODO(Faza 1-lite, 2-blok): faol buyurtma, nizo yoki qarz bo'lsa rad etish
        now = datetime.now(UTC)
        user.status = UserStatus.DELETED
        user.deleted_at = now
        await self.db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.db.flush()

    async def link_telegram_phone(
        self,
        telegram_id: int,
        raw_phone: str,
        *,
        full_name: str | None = None,
        username: str | None = None,
        language_code: str | None = None,
    ) -> User:
        """Bot requestContact orqali olgan (Telegram tasdiqlagan) raqamni akkauntga bog'laydi.

        Bitta telefon — bitta akkaunt: agar raqam bilan SMS orqali ochilgan akkaunt bo'lsa,
        Telegram ID o'sha akkauntga ko'chiriladi, bo'sh Telegram akkaunti o'chiriladi.
        """
        phone = normalize_phone(raw_phone)
        now = datetime.now(UTC)
        tg_user = await self.db.scalar(select(User).where(User.telegram_id == telegram_id))
        phone_user = await self.db.scalar(select(User).where(User.phone == phone))

        if phone_user and tg_user and phone_user.id != tg_user.id:
            if phone_user.telegram_id is not None:
                raise Conflict("Bu raqam boshqa Telegram akkauntga bog'langan", code="PHONE_TAKEN")
            if tg_user.phone is not None or tg_user.roles:
                raise Conflict("Akkauntlarni avtomatik birlashtirib bo'lmaydi", code="MERGE_REQUIRED")
            tg_user.telegram_id = None
            tg_user.status = UserStatus.DELETED
            tg_user.deleted_at = now
            await self.db.execute(update(AuthSession).where(AuthSession.user_id == tg_user.id).values(revoked_at=now))
            await self.db.flush()
            user = phone_user
            user.telegram_id = telegram_id
        elif phone_user:
            if phone_user.telegram_id not in (None, telegram_id):
                raise Conflict("Bu raqam boshqa Telegram akkauntga bog'langan", code="PHONE_TAKEN")
            user = phone_user
            user.telegram_id = telegram_id
        elif tg_user:
            user = tg_user
            user.phone = phone
        else:
            user = User(
                telegram_id=telegram_id, phone=phone, full_name=full_name, lang=Lang.from_telegram(language_code)
            )
            self.db.add(user)

        user.phone_verified_at = user.phone_verified_at or now
        user.telegram_username = username or user.telegram_username
        if not user.full_name and full_name:
            user.full_name = full_name
        await self.db.flush()
        return user
