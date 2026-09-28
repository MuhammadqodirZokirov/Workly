import hmac

from aiogram.types import Update
from fastapi import APIRouter, Header, Request, status

from workly.domain.errors import Unauthorized

from ..deps import SettingsDep

router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)


@router.post("/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    settings: SettingsDep,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    expected = settings.bot_webhook_secret.get_secret_value() if settings.bot_webhook_secret else ""
    if not expected or not secret or not hmac.compare_digest(secret, expected):
        raise Unauthorized()
    bot, dp = request.app.state.bot, request.app.state.dp
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}
