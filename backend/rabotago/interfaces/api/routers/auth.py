from fastapi import APIRouter, Depends, status

from ..deps import AuthServiceDep, ClientDep, auth_rate_limit
from ..schemas import OtpSendIn, OtpSendOut, OtpVerifyIn, RefreshIn, TelegramLoginIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(auth_rate_limit)])


@router.post("/telegram", response_model=TokenOut)
async def login_telegram(body: TelegramLoginIn, auth: AuthServiceDep, client: ClientDep):
    return TokenOut.of(await auth.login_telegram(body.init_data, client))


@router.post("/otp/send", response_model=OtpSendOut)
async def otp_send(body: OtpSendIn, auth: AuthServiceDep):
    return OtpSendOut(expires_in=await auth.send_otp(body.phone))


@router.post("/otp/verify", response_model=TokenOut)
async def otp_verify(body: OtpVerifyIn, auth: AuthServiceDep, client: ClientDep):
    return TokenOut.of(await auth.verify_otp(body.phone, body.code, client))


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, auth: AuthServiceDep):
    return TokenOut.of(await auth.refresh(body.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshIn, auth: AuthServiceDep):
    await auth.logout(body.refresh_token)
