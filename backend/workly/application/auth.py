"""Kirish: Telegram initData, SMS OTP, refresh rotatsiya (TZ 3-bo'lim)."""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Forbidden, RateLimited, Unauthorized, ValidationFailed
from workly.domain.phone import normalize_phone
from workly.domain.telegram_auth import verify_init_data
from workly.domain.users import Lang, UserStatus
from workly.infrastructure.config import Settings
from workly.infrastructure.db.models import AuthSession, User
from workly.infrastructure.security import create_access_token, hash_token, new_refresh_token
from workly.infrastructure.sms import SmsSender

TASHKENT = ZoneInfo("Asia/Tashkent")

# SMS kod qoidalari (TZ 3-bo'lim)
OTP_TTL = 120
OTP_MAX_ATTEMPTS = 5
OTP_BLOCK_SECONDS = 15 * 60
OTP_COOLDOWN = 60
OTP_DAILY_LIMIT = 5


@dataclass(frozen=True)
class ClientInfo:
    device: str | None = None
    ip: str | None = None


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(dt: datetime) -> datetime:
    # SQLite tz'ni saqlamaydi — testlarda naive datetime qaytadi
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _ensure_active(user: User) -> None:
    if user.status == UserStatus.BLOCKED:
        raise Forbidden("Akkaunt bloklangan", code="USER_BLOCKED")
    if user.status == UserStatus.DELETED:
        raise Forbidden("Akkaunt o'chirilgan", code="USER_DELETED")


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis, settings: Settings, sms: SmsSender):
        self.db, self.redis, self.settings, self.sms = db, redis, settings, sms

    # ---------- tokenlar ----------
    async def _issue(self, user: User, client: ClientInfo) -> TokenPair:
        _ensure_active(user)
        refresh = new_refresh_token()
        now = _now()
        self.db.add(
            AuthSession(
                user_id=user.id,
                refresh_hash=hash_token(refresh),
                device=client.device,
                ip=client.ip,
                created_at=now,
                last_used_at=now,
                expires_at=now + timedelta(days=self.settings.jwt_refresh_ttl_days),
            )
        )
        await self.db.flush()
        return self._pair(user, refresh)

    def _pair(self, user: User, refresh: str) -> TokenPair:
        ttl = self.settings.jwt_access_ttl_min
        access = create_access_token(user.id, self.settings.jwt_secret.get_secret_value(), ttl)
        return TokenPair(access, refresh, ttl * 60, user)

    async def refresh(self, refresh_token: str) -> TokenPair:
        session = await self.db.scalar(select(AuthSession).where(AuthSession.refresh_hash == hash_token(refresh_token)))
        if session is None:
            raise Unauthorized("Refresh token noto'g'ri", code="INVALID_REFRESH")
        if session.revoked_at is not None:
            # Eski (almashtirilgan yoki bekor qilingan) token qayta ishlatildi — o'g'irlangan bo'lishi mumkin.
            # Xato qaytgach so'rov rollback bo'ladi, shuning uchun bekor qilishni darhol commit qilamiz.
            await self._revoke_all(session.user_id)
            await self.db.commit()
            raise Unauthorized("Refresh token bekor qilingan", code="INVALID_REFRESH")
        now = _now()
        if _as_utc(session.expires_at) <= now:
            raise Unauthorized("Sessiya muddati tugagan", code="SESSION_EXPIRED")

        user = await self.db.get(User, session.user_id)
        _ensure_active(user)
        # Rotatsiya: eski yozuv bekor qilinadi, yangisi yaratiladi (qayta ishlatishni aniqlash uchun)
        session.revoked_at = now
        refresh = new_refresh_token()
        self.db.add(
            AuthSession(
                user_id=user.id,
                refresh_hash=hash_token(refresh),
                device=session.device,
                ip=session.ip,
                created_at=now,
                last_used_at=now,
                expires_at=now + timedelta(days=self.settings.jwt_refresh_ttl_days),
            )
        )
        await self.db.flush()
        return self._pair(user, refresh)

    async def logout(self, refresh_token: str) -> None:
        await self.db.execute(
            update(AuthSession)
            .where(AuthSession.refresh_hash == hash_token(refresh_token), AuthSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )

    async def _revoke_all(self, user_id: int) -> None:
        await self.db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=_now())
        )

    # ---------- Telegram Mini App ----------
    async def login_telegram(self, init_data: str, client: ClientInfo) -> TokenPair:
        tg = verify_init_data(
            init_data,
            self.settings.bot_token.get_secret_value(),
            max_age=self.settings.telegram_auth_max_age,
            now=int(time.time()),
        )
        user = await self.db.scalar(select(User).where(User.telegram_id == tg.id))
        if user is None:
            user = User(telegram_id=tg.id, full_name=tg.full_name or None, lang=Lang.from_telegram(tg.language_code))
            self.db.add(user)
        user.telegram_username = tg.username
        await self.db.flush()
        return await self._issue(user, client)

    # ---------- SMS OTP ----------
    def _code_hash(self, phone: str, code: str) -> str:
        key = self.settings.jwt_secret.get_secret_value().encode()
        return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()

    async def send_otp(self, raw_phone: str) -> int:
        """Kod yuboradi; kod amal qilish muddatini (soniya) qaytaradi."""
        phone = normalize_phone(raw_phone)
        r = self.redis
        if await r.exists(f"otp:block:{phone}"):
            raise RateLimited("Ko'p xato urinish. 15 daqiqadan keyin urinib ko'ring", code="OTP_BLOCKED")
        if not await r.set(f"otp:cooldown:{phone}", 1, ex=OTP_COOLDOWN, nx=True):
            raise RateLimited(
                "Kodni 60 soniyada bir marta so'rash mumkin",
                code="OTP_COOLDOWN",
                details={"retry_after": await r.ttl(f"otp:cooldown:{phone}")},
            )
        day_key = f"otp:daily:{phone}:{datetime.now(TASHKENT):%Y%m%d}"
        sent_today = await r.incr(day_key)
        if sent_today == 1:
            await r.expire(day_key, 86400)
        if sent_today > OTP_DAILY_LIMIT:
            raise RateLimited("Bugungi SMS limiti tugadi", code="OTP_DAILY_LIMIT")

        code = f"{secrets.randbelow(10**6):06d}"
        key = f"otp:code:{phone}"
        await r.delete(key)
        await r.hset(key, mapping={"hash": self._code_hash(phone, code), "attempts": 0})
        await r.expire(key, OTP_TTL)
        await self.sms.send(phone, f"Workly tasdiqlash kodi: {code}")
        return OTP_TTL

    async def verify_otp(self, raw_phone: str, code: str, client: ClientInfo) -> TokenPair:
        phone = normalize_phone(raw_phone)
        if not (code.isdigit() and len(code) == 6):
            raise ValidationFailed("Kod 6 xonali bo'lishi kerak", code="INVALID_OTP")
        r = self.redis
        if await r.exists(f"otp:block:{phone}"):
            raise RateLimited("Ko'p xato urinish. 15 daqiqadan keyin urinib ko'ring", code="OTP_BLOCKED")
        key = f"otp:code:{phone}"
        stored = await r.hget(key, "hash")
        if stored is None:
            raise Unauthorized("Kod muddati tugagan, yangisini so'rang", code="OTP_EXPIRED")
        if isinstance(stored, bytes):
            stored = stored.decode()
        if not hmac.compare_digest(stored, self._code_hash(phone, code)):
            attempts = await r.hincrby(key, "attempts", 1)
            if attempts >= OTP_MAX_ATTEMPTS:
                await r.delete(key)
                await r.set(f"otp:block:{phone}", 1, ex=OTP_BLOCK_SECONDS)
                raise RateLimited("Ko'p xato urinish. 15 daqiqadan keyin urinib ko'ring", code="OTP_BLOCKED")
            raise Unauthorized(
                "Kod noto'g'ri", code="OTP_INVALID", details={"attempts_left": OTP_MAX_ATTEMPTS - attempts}
            )
        await r.delete(key)

        user = await self.db.scalar(select(User).where(User.phone == phone))
        if user is None:
            user = User(phone=phone)
            self.db.add(user)
        user.phone_verified_at = user.phone_verified_at or _now()
        await self.db.flush()
        return await self._issue(user, client)
