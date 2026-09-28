"""TOTP (RFC 6238) — admin panel 2FA (TZ 3, 16-bo'limlar). Google Authenticator, Authy va h.k. bilan mos."""

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote

STEP = 30
DIGITS = 6


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    return base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)


def code_at(secret: str, timestep: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", timestep), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def matching_step(secret: str, code: str, now: float, window: int = 1) -> int | None:
    """Kod to'g'ri bo'lsa — mos vaqt qadami (qayta ishlatishni oldini olish uchun), aks holda None.
    ±1 qadam (30 s) — telefon soati biroz farq qilishi mumkin."""
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    current = int(now // STEP)
    for step in range(current - window, current + window + 1):
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def otpauth_uri(secret: str, account: str, issuer: str = "Workly") -> str:
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"
