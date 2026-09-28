import pytest
from sqlalchemy import select

from workly.infrastructure.db.models import AuditLog, StateTransition

API = "/api/v1"


@pytest.fixture
async def employer(client, login, redis):
    async def _make(phone="+998971234567", consents=True):
        await redis.delete(f"otp:cooldown:{phone}")
        body, h = await login(phone)
        await client.post(f"{API}/me/roles", json={"role": "employer"}, headers=h)
        await client.patch(f"{API}/me", json={"full_name": "Aziz Karimov"}, headers=h)
        if consents:
            await client.post(
                f"{API}/me/consents",
                headers=h,
                json={"items": [{"doc_type": d, "version": "1.0"} for d in ("terms", "privacy", "employer_contract")]},
            )
        return body["user"]["id"], h

    return _make


@pytest.fixture
async def district_id(client):
    return (await client.get(f"{API}/catalog/districts")).json()[0]["id"]


def business(district_id, **kw):
    return {
        "type": "business",
        "company_name": "  Qurilish  Servis MChJ",
        "stir": "301 234 567",
        "activity": "Qurilish",
        "address_text": "Chilonzor 9-kvartal",
        "district_id": district_id,
        "point": {"lat": 41.28, "lon": 69.2},
        **kw,
    }


async def test_employer_role_required(client, login):
    _, h = await login()
    r = await client.get(f"{API}/employer/profile", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "NOT_AN_EMPLOYER"


async def test_individual_default(client, employer):
    _, h = await employer()
    p = (await client.get(f"{API}/employer/profile", headers=h)).json()
    assert p["type"] == "individual" and p["full_name"] == "Aziz Karimov"
    assert p["business_verification"] is None and p["badges"] == []
    # jismoniy shaxsga kompaniya maydonlari mumkin emas
    r = await client.put(f"{API}/employer/profile", json={"stir": "301234567"}, headers=h)
    assert r.status_code == 422 and r.json()["code"] == "NOT_A_BUSINESS"
    # manzil ixtiyoriy, lekin kiritilsa — to'g'ri tuman
    r = await client.put(f"{API}/employer/profile", json={"district_id": 99999}, headers=h)
    assert r.json()["code"] == "INVALID_DISTRICT"


async def test_business_profile(client, employer, district_id):
    _, h = await employer()
    r = await client.put(f"{API}/employer/profile", json=business(district_id), headers=h)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["company_name"] == "Qurilish Servis MChJ" and p["stir"] == "301234567"
    assert p["business_verification"]["status"] == "not_submitted"
    r = await client.put(f"{API}/employer/profile", json={"stir": "12345"}, headers=h)
    assert r.json()["code"] == "INVALID_STIR"
    # null — nuqtani o'chiradi, qolgani o'zgarmaydi
    p = (await client.put(f"{API}/employer/profile", json={"point": None}, headers=h)).json()
    assert p["point"] is None and p["district_id"] == district_id


async def test_business_submit_incomplete(client, employer):
    _, h = await employer(consents=False)
    await client.put(f"{API}/employer/profile", json={"type": "business", "company_name": "X"}, headers=h)
    r = await client.post(f"{API}/employer/verification", headers=h)
    assert r.json()["code"] == "PROFILE_INCOMPLETE"
    assert {"stir", "activity", "address_text", "district_id", "consent:employer_contract"} <= set(r.json()["details"])


async def test_individual_cannot_submit(client, employer):
    _, h = await employer()
    r = await client.post(f"{API}/employer/verification", headers=h)
    assert r.json()["code"] == "NOT_A_BUSINESS"


async def test_business_moderation(client, employer, district_id, moderator, notifier, db):
    uid, h = await employer()
    await client.put(f"{API}/employer/profile", json=business(district_id), headers=h)
    r = await client.post(f"{API}/employer/verification", headers=h)
    assert r.json()["business_verification"]["status"] == "pending"

    # tekshiruvda kompaniya ma'lumoti qulflanadi
    r = await client.put(f"{API}/employer/profile", json={"stir": "309999999"}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "PROFILE_LOCKED"
    r = await client.put(f"{API}/employer/profile", json={"type": "individual"}, headers=h)
    assert r.status_code == 409
    assert (
        await client.put(f"{API}/employer/profile", json={"address_text": "Yangi manzil"}, headers=h)
    ).status_code == 200

    _, mh = moderator
    assert (await client.get(f"{API}/admin/employers", headers=h)).status_code == 403
    q = (await client.get(f"{API}/admin/employers", headers=mh)).json()
    assert q[0]["user_id"] == uid and q[0]["stir"] == "301234567" and q[0]["responsible"] == "Aziz Karimov"

    r = await client.post(f"{API}/admin/employers/{uid}/reject", json={"reason": "other"}, headers=mh)
    assert r.json()["code"] == "COMMENT_REQUIRED"
    r = await client.post(f"{API}/admin/employers/{uid}/reject", json={"reason": "stir_invalid"}, headers=mh)
    assert r.json()["business_verification"]["status"] == "rejected"

    # tuzatib qayta yuboradi, moderator tasdiqlaydi
    await client.put(f"{API}/employer/profile", json={"stir": "302222222"}, headers=h)
    await client.post(f"{API}/employer/verification", headers=h)
    r = await client.post(f"{API}/admin/employers/{uid}/approve", headers=mh)
    p = r.json()
    assert p["business_verification"]["status"] == "verified" and p["badges"] == ["verified_employer"]
    assert notifier.calls == [("business", uid, False, "stir_invalid"), ("business", uid, True, None)]

    states = [
        (t.from_state, t.to_state)
        for t in (
            await db.scalars(
                select(StateTransition)
                .where(StateTransition.object_type == "business_verification")
                .order_by(StateTransition.id)
            )
        ).all()
    ]
    assert states == [
        ("not_submitted", "pending"),
        ("pending", "rejected"),
        ("rejected", "pending"),
        ("pending", "verified"),
    ]
    actions = [a.action for a in (await db.scalars(select(AuditLog).order_by(AuditLog.id))).all()]
    assert actions == ["business.reject", "business.approve"]


async def test_same_stir_shown(client, employer, district_id, moderator):
    a, ha = await employer("+998971000001")
    b, hb = await employer("+998971000002")
    for h in (ha, hb):
        await client.put(f"{API}/employer/profile", json=business(district_id), headers=h)
        await client.post(f"{API}/employer/verification", headers=h)
    _, mh = moderator
    q = {i["user_id"]: i for i in (await client.get(f"{API}/admin/employers", headers=mh)).json()}
    assert q[a]["same_stir_user_ids"] == [b] and q[b]["same_stir_user_ids"] == [a]


async def test_switch_to_individual_clears_company(client, employer, district_id):
    _, h = await employer()
    await client.put(f"{API}/employer/profile", json=business(district_id), headers=h)
    p = (await client.put(f"{API}/employer/profile", json={"type": "individual"}, headers=h)).json()
    assert p["type"] == "individual" and p["company_name"] is None and p["stir"] is None
    assert p["address_text"] == "Chilonzor 9-kvartal"  # manzil qoladi
