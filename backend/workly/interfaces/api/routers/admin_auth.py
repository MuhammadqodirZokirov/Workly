from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from workly.application.admin_auth import AdminAuthService
from workly.domain.users import Role

from ..deps import CipherDep, CurrentUser, DbDep, RedisDep, SettingsDep, auth_rate_limit, client_ip, require_roles
from ..schemas import MeOut

router = APIRouter(prefix="/admin", tags=["admin"])


class TotpIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class AdminTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/auth/totp", response_model=AdminTokenOut, dependencies=[Depends(auth_rate_limit)])
async def totp(
    body: TotpIn,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    settings: SettingsDep,
    cipher: CipherDep,
    request: Request,
):
    """Oddiy kirishdan keyin (SMS/Telegram) — TOTP kodi bilan admin sessiyasi (8 soat)."""
    token, ttl = await AdminAuthService(db, redis, settings, cipher).verify(user, body.code, client_ip(request))
    return AdminTokenOut(access_token=token, expires_in=ttl)


@router.get("/me", response_model=MeOut, dependencies=[Depends(require_roles(Role.MODERATOR, Role.ADMIN, mfa=True))])
async def admin_me(user: CurrentUser):
    return MeOut.of(user)
