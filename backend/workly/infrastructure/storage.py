"""Fayl saqlash. Faza 1-lite: diskda shifrlangan holda; o'sishda MinIO (S3) ga almashtiriladi."""

import asyncio
import hashlib
import hmac
import secrets
import time
from pathlib import Path
from typing import Protocol

from .crypto import DataCipher


class FileStorage(Protocol):
    async def save(self, data: bytes, prefix: str) -> str: ...
    async def read(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


class EncryptedLocalStorage:
    def __init__(self, root: str, cipher: DataCipher):
        self.root = Path(root)
        self.cipher = cipher

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Noto'g'ri fayl kaliti")
        return path

    async def save(self, data: bytes, prefix: str) -> str:
        key = f"{prefix}/{secrets.token_hex(16)}"
        path = self._path(key)
        encrypted = self.cipher.encrypt(data)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encrypted)

        await asyncio.to_thread(_write)
        return key

    async def read(self, key: str) -> bytes:
        encrypted = await asyncio.to_thread(self._path(key).read_bytes)
        return self.cipher.decrypt(encrypted)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, True)


def sign_file_url(key: str, secret: str, ttl: int, now: int | None = None) -> tuple[int, str]:
    exp = (now or int(time.time())) + ttl
    sig = hmac.new(secret.encode(), f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()
    return exp, sig


def verify_file_signature(key: str, exp: int, sig: str, secret: str, now: int | None = None) -> bool:
    if exp < (now or int(time.time())):
        return False
    expected = hmac.new(secret.encode(), f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def sniff_image(data: bytes) -> str | None:
    """Fayl turini kengaytmaga emas, sarlavhaga qarab aniqlaydi."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None
