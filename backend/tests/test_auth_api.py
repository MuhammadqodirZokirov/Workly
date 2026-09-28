from sqlalchemy import select

from rabotago.infrastructure.db.models import AuthSession

from .test_domain import TG_USER, make_init_data

API = "/api/v1"


async def test_otp_login_creates_user(client, sms, login):
    body, headers = await login("90 123 45 67")
    assert body["user"]["phone"] == "+998901234567"
    assert body["user"]["phone_verified"] is True
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert sms.sent[0][0] == "+998901234567"

    r = await client.get(f"{API}/me", headers=headers)
    assert r.status_code == 200 and r.json()["id"] == body["user"]["id"]


async def test_otp_same_phone_same_user(login, redis):
    a, _ = await login()
    await redis.delete("otp:cooldown:+998901234567")
    b, _ = await login()
    assert a["user"]["id"] == b["user"]["id"]


async def test_otp_cooldown(client):
    assert (await client.post(f"{API}/auth/otp/send", json={"phone": "+998901111111"})).status_code == 200
    r = await client.post(f"{API}/auth/otp/send", json={"phone": "+998901111111"})
    assert r.status_code == 429 and r.json()["code"] == "OTP_COOLDOWN"


async def test_otp_daily_limit(client, redis):
    phone = "+998901111112"
    for _ in range(5):
        assert (await client.post(f"{API}/auth/otp/send", json={"phone": phone})).status_code == 200
        await redis.delete(f"otp:cooldown:{phone}")
    r = await client.post(f"{API}/auth/otp/send", json={"phone": phone})
    assert r.json()["code"] == "OTP_DAILY_LIMIT"


async def test_otp_wrong_code_blocks_after_5(client, sms):
    phone = "+998901111113"
    await client.post(f"{API}/auth/otp/send", json={"phone": phone})
    good = sms.last_code()
    wrong = "000000" if good != "000000" else "111111"
    for left in (4, 3, 2, 1):
        r = await client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": wrong})
        assert r.status_code == 401 and r.json()["details"]["attempts_left"] == left
    r = await client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": wrong})
    assert r.json()["code"] == "OTP_BLOCKED"
    # to'g'ri kod ham endi ishlamaydi va yangi kod so'rab bo'lmaydi
    r = await client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": good})
    assert r.json()["code"] == "OTP_BLOCKED"
    r = await client.post(f"{API}/auth/otp/send", json={"phone": phone})
    assert r.json()["code"] == "OTP_BLOCKED"


async def test_otp_code_single_use(client, sms):
    phone = "+998901111114"
    await client.post(f"{API}/auth/otp/send", json={"phone": phone})
    code = sms.last_code()
    assert (await client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})).status_code == 200
    r = await client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.json()["code"] == "OTP_EXPIRED"


async def test_invalid_phone(client):
    r = await client.post(f"{API}/auth/otp/send", json={"phone": "+7 900 123 45 67"})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_PHONE"


async def test_telegram_login(client):
    r = await client.post(f"{API}/auth/telegram", json={"init_data": make_init_data(TG_USER)})
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["telegram_id"] == 777 and user["lang"] == "ru" and user["phone"] is None
    r2 = await client.post(f"{API}/auth/telegram", json={"init_data": make_init_data(TG_USER)})
    assert r2.json()["user"]["id"] == user["id"]


async def test_telegram_login_bad_hash(client):
    r = await client.post(f"{API}/auth/telegram", json={"init_data": make_init_data(TG_USER, token="1:bad")})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_INIT_DATA"


async def test_refresh_rotation_and_reuse_detection(client, login, db):
    body, _ = await login()
    old = body["refresh_token"]
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    assert new != old

    # eski token qayta ishlatilsa — barcha sessiyalar bekor qilinadi
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 401
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": new})
    assert r.status_code == 401
    active = (await db.scalars(select(AuthSession).where(AuthSession.revoked_at.is_(None)))).all()
    assert active == []


async def test_logout(client, login):
    body, _ = await login()
    assert (await client.post(f"{API}/auth/logout", json={"refresh_token": body["refresh_token"]})).status_code == 204
    r = await client.post(f"{API}/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert r.status_code == 401


async def test_me_requires_token(client):
    assert (await client.get(f"{API}/me")).status_code == 401
    r = await client.get(f"{API}/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401 and r.json()["code"] == "INVALID_TOKEN"


async def test_auth_rate_limit(app, client):
    app.state.settings = app.state.settings.model_copy(update={"auth_rate_limit_per_min": 2})
    codes = [(await client.post(f"{API}/auth/refresh", json={"refresh_token": "x"})).status_code for _ in range(3)]
    assert codes == [401, 401, 429]
