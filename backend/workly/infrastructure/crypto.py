import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


class DataCipher:
    """Shaxsiy ma'lumotlarni shifrlash (Fernet: AES-128-CBC + HMAC) va takrorni topish uchun kalitli hash."""

    def __init__(self, encryption_key: str, hash_key: str):
        self._fernet = Fernet(encryption_key.encode())
        self._hash_key = hash_key.encode()

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        try:
            return self._fernet.decrypt(token)
        except InvalidToken:
            raise ValueError("Shifrni ochib bo'lmadi (kalit noto'g'ri yoki ma'lumot buzilgan)") from None

    def encrypt_str(self, value: str) -> str:
        return self.encrypt(value.encode()).decode()

    def decrypt_str(self, token: str) -> str:
        return self.decrypt(token.encode()).decode()

    def keyed_hash(self, value: str) -> str:
        return hmac.new(self._hash_key, value.encode(), hashlib.sha256).hexdigest()
