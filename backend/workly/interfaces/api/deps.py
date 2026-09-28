from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from workly.application.auth import AuthService, ClientInfo
from workly.application.notifications import Notifier
from workly.domain.errors import Forbidden, RateLimited, Unauthorized
from workly.domain.users import Role, UserStatus
from workly.infrastructure.config import Settings
from workly.infrastructure.crypto import DataCipher
from workly.infrastructure.db.models import User
from workly.infrastructure.db.session import session_scope
from workly.infrastructure.security import decode_access_token
from workly.infrastructure.storage import FileStorage


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in session_scope(request.app.state.maker):
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
RedisDep = Annotated[Redis, Depends(get_redis)]
DbDep = Annotated[AsyncSession, Depends(get_db)]


def get_client_info(request: Request) -> ClientInfo:
    ua = request.headers.get("user-agent")
    return ClientInfo(device=ua[:200] if ua else None, ip=request.client.host if request.client else None)


ClientDep = Annotated[ClientInfo, Depends(get_client_info)]


def get_auth_service(request: Request, db: DbDep, redis: RedisDep, settings: SettingsDep) -> AuthService:
    return AuthService(db, redis, settings, request.app.state.sms)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def auth_rate_limit(request: Request, redis: RedisDep, settings: SettingsDep) -> None:
    """Auth endpointlari uchun IP bo'yicha daqiqalik limit (TZ 18-bo'lim)."""
    ip = request.client.host if request.client else "unknown"
    key = f"rl:auth:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60)
    if count > settings.auth_rate_limit_per_min:
        raise RateLimited(details={"retry_after": await redis.ttl(key)})


_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DbDep,
    settings: SettingsDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise Unauthorized()
    user_id = decode_access_token(creds.credentials, settings.jwt_secret.get_secret_value())
    user = await db.get(User, user_id)
    if user is None or user.status == UserStatus.DELETED:
        raise Unauthorized()
    if user.status == UserStatus.BLOCKED:
        raise Forbidden("Akkaunt bloklangan", code="USER_BLOCKED")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    """RBAC: foydalanuvchida kamida bitta rol bo'lishi kerak (super admin — hamma joyga)."""

    async def checker(user: CurrentUser) -> User:
        names = set(user.role_names)
        if Role.SUPER_ADMIN not in names and names.isdisjoint(roles):
            raise Forbidden()
        return user

    return checker


def get_cipher(request: Request) -> DataCipher:
    return request.app.state.cipher


def get_storage(request: Request) -> FileStorage:
    return request.app.state.storage


def get_notifier(request: Request) -> Notifier:
    return request.app.state.notifier


CipherDep = Annotated[DataCipher, Depends(get_cipher)]
StorageDep = Annotated[FileStorage, Depends(get_storage)]
NotifierDep = Annotated[Notifier, Depends(get_notifier)]
Moderator = Annotated[User, Depends(require_roles(Role.MODERATOR, Role.ADMIN))]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
