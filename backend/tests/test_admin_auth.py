import time

from sqlalchemy import select

from workly.domain.totp import code_at, matching_step
from workly.infrastructure.db.models import AuditLog, User, UserRole

API = "/api/v1"


async def _staff(client, login, db, redis, app, role="moderator", phone="+998909999998"):
    from workly.application.admin_auth import AdminAuthService

    await redis.delete(f"otp:cooldown:{phone}")
    body, h = await login(phone)
    db.add(UserRole(user_id=body["user"]["id"], role=role))
    await db.commit()
    user = await db.get(User, body["user"]["id"])
    await db.refresh(user)
    uri = await AdminAuthService(db, redis, app.state.settings, app.state.cipher).setup(user)
    await db.commit()
    return body["user"]["id"], h, uri.split("secret=")[1].split("&")[0]


def test_totp_window():
    secret = "JBSWY3DPEHPK3PXP"
    now = 1_790_000_000
    step = now // 30
    assert matching_step(secret, code_at(secret, step), now) == step
    assert matching_step(secret, code_at(secret, step - 1), now) == step - 1  # soat farqi ±30 s
    assert matching_step(secret, code_at(secret, step - 3), now) is None
    assert matching_step(secret, "abc123", now) is None


async def test_admin_endpoints_require_mfa(client, login, db, redis, app):
    uid, h, secret = await _staff(client, login, db, redis, app)
    # SMS bilan kirgan moderator hujjatlarni ko'ra olmaydi
    r = await client.get(f"{API}/admin/verifications", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "MFA_REQUIRED"

    code = code_at(secret, int(time.time() // 30))
    r = await client.post(f"{API}/admin/auth/totp", json={"code": code}, headers=h)
    assert r.status_code == 200 and r.json()["expires_in"] == 8 * 3600
    mh = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get(f"{API}/admin/verifications", headers=mh)).status_code == 200
    assert (await client.get(f"{API}/admin/me", headers=mh)).json()["id"] == uid

    # bir kodni qayta ishlatib bo'lmaydi
    r = await client.post(f"{API}/admin/auth/totp", json={"code": code}, headers=h)
    assert r.json()["code"] == "TOTP_INVALID"


async def test_totp_blocks_after_5_fails(client, login, db, redis, app):
    uid, h, secret = await _staff(client, login, db, redis, app)
    good = code_at(secret, int(time.time() // 30))
    bad = "000000" if good != "000000" else "111111"
    for _ in range(5):
        r = await client.post(f"{API}/admin/auth/totp", json={"code": bad}, headers=h)
    assert r.json()["code"] == "TOTP_INVALID"
    r = await client.post(f"{API}/admin/auth/totp", json={"code": good}, headers=h)
    assert r.status_code == 429 and r.json()["code"] == "TOTP_BLOCKED"
    fails = (await db.scalars(select(AuditLog).where(AuditLog.action == "admin.totp_fail"))).all()
    assert len(fails) == 5  # rollback'dan keyin ham saqlangan


async def test_non_staff_and_unset(client, login, db, redis):
    _, h = await login()
    r = await client.post(f"{API}/admin/auth/totp", json={"code": "123456"}, headers=h)
    assert r.json()["code"] == "NOT_STAFF"

    # alohida foydalanuvchi: SQLite testlarida xato bergan so'rovning rollback'i umumiy ulanishga ta'sir qiladi
    await redis.delete("otp:cooldown:+998909999997")
    body, h2 = await login("+998909999997")
    db.add(UserRole(user_id=body["user"]["id"], role="moderator"))
    await db.commit()
    r = await client.post(f"{API}/admin/auth/totp", json={"code": "123456"}, headers=h2)
    assert r.json()["code"] == "TOTP_NOT_SET"


async def test_secret_encrypted_at_rest(client, login, db, redis, app):
    uid, _, secret = await _staff(client, login, db, redis, app)
    user = await db.get(User, uid)
    await db.refresh(user)
    assert user.totp_secret_enc and secret not in user.totp_secret_enc
