"""Admin panel 2FA: TOTP (TZ 3, 16). Kirish: SMS/Telegram + TOTP → 8 soatlik "mfa" token."""

import time
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Forbidden, RateLimited, Unauthorized
from workly.domain.totp import STEP, generate_secret, matching_step, otpauth_uri
from workly.domain.users import Role
from workly.infrastructure.config import Settings
from workly.infrastructure.crypto import DataCipher
from workly.infrastructure.db.models import User
from workly.infrastructure.security import create_access_token

from .audit import audit

STAFF_ROLES = {Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN}
MAX_FAILS = 5
BLOCK_SECONDS = 15 * 60


def is_staff(user: User) -> bool:
    return bool(STAFF_ROLES & set(user.role_names))


class AdminAuthService:
    def __init__(self, db: AsyncSession, redis: Redis, settings: Settings, cipher: DataCipher):
        self.db, self.redis, self.settings, self.cipher = db, redis, settings, cipher

    async def setup(self, user: User) -> str:
        """Yangi TOTP siri (CLI orqali super admin beradi). otpauth:// URI qaytaradi — QR kod uchun."""
        if not is_staff(user):
            raise Forbidden("Faqat xodimlar uchun", code="NOT_STAFF")
        secret = generate_secret()
        user.totp_secret_enc = self.cipher.encrypt_str(secret)
        user.totp_enabled_at = datetime.now(UTC)
        audit(self.db, None, "admin.totp_setup", "user", user.id)
        await self.db.flush()
        return otpauth_uri(secret, user.phone or f"user{user.id}")

    async def verify(self, user: User, code: str, ip: str | None, now: float | None = None) -> tuple[str, int]:
        if not is_staff(user):
            raise Forbidden("Faqat xodimlar uchun", code="NOT_STAFF")
        if not user.totp_secret_enc:
            raise Forbidden("2FA sozlanmagan — super adminga murojaat qiling", code="TOTP_NOT_SET")
        block_key, fail_key = f"totp:block:{user.id}", f"totp:fail:{user.id}"
        if await self.redis.exists(block_key):
            raise RateLimited("Ko'p xato urinish. 15 daqiqadan keyin", code="TOTP_BLOCKED")

        now = now if now is not None else time.time()
        step = matching_step(self.cipher.decrypt_str(user.totp_secret_enc), code.strip(), now)
        # Bir kodni ikki marta ishlatib bo'lmaydi (qayta yuborish hujumi)
        used = await self.redis.get(f"totp:last:{user.id}")
        if step is not None and used is not None and int(used) >= step:
            step = None
        if step is None:
            fails = await self.redis.incr(fail_key)
            await self.redis.expire(fail_key, BLOCK_SECONDS)
            if fails >= MAX_FAILS:
                await self.redis.set(block_key, 1, ex=BLOCK_SECONDS)
                await self.redis.delete(fail_key)
            audit(self.db, user.id, "admin.totp_fail", "user", user.id, ip=ip)
            await self.db.commit()  # xato qaytgach rollback bo'ladi — audit saqlansin
            raise Unauthorized("Kod noto'g'ri", code="TOTP_INVALID")

        await self.redis.set(f"totp:last:{user.id}", step, ex=STEP * 4)
        await self.redis.delete(fail_key)
        audit(self.db, user.id, "admin.login", "user", user.id, ip=ip)
        ttl_min = self.settings.admin_session_hours * 60
        token = create_access_token(user.id, self.settings.jwt_secret.get_secret_value(), ttl_min, mfa=True)
        return token, ttl_min * 60
