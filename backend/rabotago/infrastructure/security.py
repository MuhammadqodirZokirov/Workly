import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from rabotago.domain.errors import Unauthorized

ALGORITHM = "HS256"


def create_access_token(user_id: int, secret: str, ttl_min: int, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    payload = {"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(minutes=ttl_min)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> int:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise Unauthorized("Token muddati tugagan", code="TOKEN_EXPIRED") from None
    except jwt.PyJWTError:
        raise Unauthorized("Token noto'g'ri", code="INVALID_TOKEN") from None
    if payload.get("type") != "access":
        raise Unauthorized("Token noto'g'ri", code="INVALID_TOKEN")
    return int(payload["sub"])


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
