import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from workly.domain.errors import Unauthorized, ValidationFailed
from workly.domain.phone import normalize_phone
from workly.domain.telegram_auth import verify_init_data
from workly.domain.translit import latin_to_cyrillic

from .conftest import BOT_TOKEN


def make_init_data(user: dict, *, auth_date: int | None = None, token: str = BOT_TOKEN) -> str:
    data = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAH", "user": json.dumps(user)}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


TG_USER = {"id": 777, "first_name": "Jasur", "last_name": "T", "username": "jasur", "language_code": "ru"}


def test_init_data_valid():
    u = verify_init_data(make_init_data(TG_USER), BOT_TOKEN, max_age=86400, now=int(time.time()))
    assert (u.id, u.full_name, u.language_code) == (777, "Jasur T", "ru")


def test_init_data_wrong_token():
    with pytest.raises(Unauthorized):
        verify_init_data(make_init_data(TG_USER, token="1:other"), BOT_TOKEN, max_age=86400, now=int(time.time()))


def test_init_data_tampered():
    raw = make_init_data(TG_USER).replace("777", "778")
    with pytest.raises(Unauthorized):
        verify_init_data(raw, BOT_TOKEN, max_age=86400, now=int(time.time()))


def test_init_data_expired():
    old = int(time.time()) - 86401
    with pytest.raises(Unauthorized) as e:
        verify_init_data(make_init_data(TG_USER, auth_date=old), BOT_TOKEN, max_age=86400, now=int(time.time()))
    assert e.value.code == "INIT_DATA_EXPIRED"


@pytest.mark.parametrize("raw", ["+998 90 123-45-67", "998901234567", "901234567", "(90) 123 45 67"])
def test_phone_ok(raw):
    assert normalize_phone(raw) == "+998901234567"


@pytest.mark.parametrize("raw", ["", "12345", "+79001234567", "+9989012345678"])
def test_phone_bad(raw):
    with pytest.raises(ValidationFailed):
        normalize_phone(raw)


@pytest.mark.parametrize(
    "latn,cyrl",
    [
        ("Qurilish", "Қурилиш"),
        ("G'isht teruvchi", "Ғишт терувчи"),
        ("O'zbekiston", "Ўзбекистон"),
        ("Ta'mirdan keyin", "Таъмирдан кейин"),
        ("Elektrik", "Электрик"),
        ("Yangihayot", "Янгиҳаёт"),
        ("Mirzo Ulugʻbek", "Мирзо Улуғбек"),
        ("SHAHAR", "ШАҲАР"),
    ],
)
def test_translit(latn, cyrl):
    assert latin_to_cyrillic(latn) == cyrl


def test_prod_settings_guard():
    import pytest
    from pydantic import ValidationError

    from workly.infrastructure.config import Settings

    base = dict(
        jwt_secret="almashtiring-kamida-32-belgili-tasodifiy-satr",
        data_encryption_key="k",
        data_hash_key="",
        bot_token="1:x",
        _env_file=None,
    )
    Settings(**base)  # dev — namuna qiymatlar mumkin
    with pytest.raises(ValidationError) as e:
        Settings(**base, env="prod")
    msg = str(e.value)
    assert "JWT_SECRET" in msg and "SMS_PROVIDER" in msg and "WEBAPP_URL" in msg and "DATA_HASH_KEY" in msg
    Settings(
        **{**base, "jwt_secret": "x" * 40, "data_hash_key": "h"},
        env="prod",
        sms_provider="eskiz",
        webapp_url="https://app.workly.uz",
        database_url="postgresql+asyncpg://w:strong@db/w",
    )
