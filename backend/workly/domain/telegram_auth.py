"""Telegram Mini App initData tekshiruvi (HMAC-SHA256, bot tokeni bilan).

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from urllib.parse import parse_qsl

from .errors import Unauthorized


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)


def verify_init_data(init_data: str, bot_token: str, *, max_age: int, now: int) -> TelegramUser:
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        raise Unauthorized("initData noto'g'ri", code="INVALID_INIT_DATA") from None

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise Unauthorized("initData imzosiz", code="INVALID_INIT_DATA")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise Unauthorized("initData imzosi noto'g'ri", code="INVALID_INIT_DATA")

    try:
        auth_date = int(data["auth_date"])
        user = json.loads(data["user"])
    except (KeyError, ValueError):
        raise Unauthorized("initData to'liq emas", code="INVALID_INIT_DATA") from None

    if now - auth_date > max_age:
        raise Unauthorized("initData eskirgan", code="INIT_DATA_EXPIRED")

    return TelegramUser(
        id=int(user["id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name"),
        username=user.get("username"),
        language_code=user.get("language_code"),
    )
