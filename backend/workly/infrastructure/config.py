from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://workly:workly@localhost:5432/workly"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: SecretStr
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 30

    # Telegram
    bot_token: SecretStr
    bot_mode: Literal["polling", "webhook", "off"] = "polling"
    public_base_url: str | None = None  # webhook uchun, masalan https://api.workly.uz
    bot_webhook_secret: SecretStr | None = None
    webapp_url: str = "https://example.com"
    telegram_auth_max_age: int = 24 * 3600
    admins: list[int] = []  # JSON: [123, 456]
    # Alohida admin bot (TZ 16): kategoriya, narx, hudud, signallar. Bo'sh bo'lsa — signallar asosiy botdan
    admin_bot_token: SecretStr | None = None

    # SMS
    sms_provider: Literal["console", "eskiz"] = "console"
    eskiz_email: str | None = None
    eskiz_password: SecretStr | None = None
    eskiz_from: str = "4546"

    # IP bo'yicha auth so'rovlari (TZ 18). Bitta Wi-Fi/mobil operator NAT ortida ko'p foydalanuvchi
    # bo'lishi mumkin — 30. Brute-force'dan asosiy himoya raqam bo'yicha: 60 s da 1 kod, kuniga 5 ta,
    # 5 xato — 15 daqiqa blok.
    auth_rate_limit_per_min: int = 30

    # Shaxsiy ma'lumotlar (TZ 19-bo'lim)
    # Fernet kaliti. Yaratish:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    data_encryption_key: SecretStr
    data_hash_key: SecretStr  # hujjat raqami hash'i uchun (takrorni topish)
    media_dir: str = "./media"  # Faza 1-lite: shifrlangan fayllar diskda; o'sishda MinIO
    signed_url_ttl: int = 300

    # Faza 1-lite pilot bepul: komissiya yo'q (TZ 22). YaTT ochilgach yoqiladi.
    commission_enabled: bool = False
    # Ko'p kunlik buyurtma: har kun alohida check-in va yakun (TZ 6, OS-9) hali yo'q — pilotda o'chiq
    multi_day_enabled: bool = False

    # Admin panel: TOTP 2FA majburiy (TZ 3); sessiya — bitta smena
    admin_mfa_required: bool = True
    admin_session_hours: int = 8
    scheduler_enabled: bool = True
    max_upload_mb: int = 5
    cors_origins: list[str] = []

    @model_validator(mode="after")
    def _prod_guard(self) -> "Settings":
        """Production'da namuna qiymatlar va xavfli rejimlar bilan ishga tushmaslik."""
        if self.env != "prod":
            return self
        problems = []
        jwt = self.jwt_secret.get_secret_value()
        if len(jwt) < 32 or "almashtiring" in jwt:
            problems.append("JWT_SECRET: kamida 32 belgili tasodifiy satr")
        if "almashtiring" in self.database_url:
            problems.append("POSTGRES_PASSWORD: namuna parol")
        if not self.data_hash_key.get_secret_value():
            problems.append("DATA_HASH_KEY bo'sh")
        if self.sms_provider == "console":
            problems.append("SMS_PROVIDER=console — kodlar logga yoziladi; prod'da eskiz kerak")
        if self.bot_mode == "webhook" and not (self.public_base_url and self.bot_webhook_secret):
            problems.append("BOT_MODE=webhook: PUBLIC_BASE_URL va BOT_WEBHOOK_SECRET kerak")
        if not self.webapp_url.startswith("https://") or "example" in self.webapp_url:
            problems.append("WEBAPP_URL: haqiqiy https manzil")
        if not self.admin_mfa_required:
            problems.append("ADMIN_MFA_REQUIRED=false prod'da mumkin emas")
        if problems:
            raise ValueError("Production sozlamalari noto'g'ri:\n- " + "\n- ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
