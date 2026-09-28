from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from workly.infrastructure.db.models import Order, StateTransition, UserRole

API = "/api/v1"
TASHKENT = ZoneInfo("Asia/Tashkent")


@pytest.fixture
async def emp(client, login, redis):
    await redis.delete("otp:cooldown:+998971234567")
    body, h = await login("+998971234567")
    await client.post(f"{API}/me/roles", json={"role": "employer"}, headers=h)
    return body["user"]["id"], h


@pytest.fixture
async def ids(client):
    cats = {c["code"]: c for c in (await client.get(f"{API}/catalog/categories")).json()}
    district = (await client.get(f"{API}/catalog/districts")).json()[0]["id"]
    return cats, district


def order_body(cats, district, **kw):
    c = cats["construction"]
    tomorrow = (datetime.now(TASHKENT) + timedelta(days=1)).date().isoformat()
    body = {
        "category_id": c["id"],
        "specialization_id": c["specializations"][0]["id"],
        "workers": 3,
        "date": tomorrow,
        "start_time": "08:00",
        "duration": "day",
        "point": {"lat": 41.3, "lon": 69.2},
        "district_id": district,
        "address_text": "Chilonzor 9-kvartal, 12-uy",
        "description": "Beton quyish",
    }
    body.update(kw)
    return body


async def place(client, h, body, key="idem-key-0001"):
    q = await client.post(f"{API}/orders/quote", json=body, headers=h)
    assert q.status_code == 200, q.text
    r = await client.post(
        f"{API}/orders",
        json={"quote_id": q.json()["quote_id"], "accept_rules": True},
        headers={**h, "Idempotency-Key": key},
    )
    return q.json(), r


async def test_quote_and_create(client, emp, ids, db):
    cats, district = ids
    _, h = emp
    quote, r = await place(client, h, order_body(cats, district))
    assert quote["price"]["employer_total"] == 450_000 and quote["price"]["worker_net"] == 150_000  # pilot
    assert quote["night"] is False and quote["needs_approval"] is False and quote["cancellation_policy"]
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["status"] == "matching" and len(o["assignments"]) == 3
    assert all(a["status"] == "open" for a in o["assignments"])
    assert o["price"]["worker_price"] == 150_000
    tr = (await db.scalars(select(StateTransition).where(StateTransition.object_type == "order"))).all()
    assert [(t.from_state, t.to_state) for t in tr] == [(None, "matching")]


async def test_master_price_and_night(client, emp, ids):
    cats, district = ids
    _, h = emp
    master = next(s for s in cats["construction"]["specializations"] if s["name"]["uz_latn"] == "Usta")
    q = (
        await client.post(
            f"{API}/orders/quote",
            headers=h,
            json=order_body(cats, district, specialization_id=master["id"], workers=1, start_time="23:00"),
        )
    ).json()
    assert q["price"]["worker_price"] == 250_000 and q["night"] is True


async def test_idempotency(client, emp, ids, db):
    cats, district = ids
    _, h = emp
    q = (await client.post(f"{API}/orders/quote", json=order_body(cats, district), headers=h)).json()
    hdr = {**h, "Idempotency-Key": "same-key-123"}
    body = {"quote_id": q["quote_id"], "accept_rules": True}
    r1 = await client.post(f"{API}/orders", json=body, headers=hdr)
    r2 = await client.post(f"{API}/orders", json=body, headers=hdr)
    assert r1.status_code == r2.status_code == 201 and r1.json()["id"] == r2.json()["id"]
    assert len((await db.scalars(select(Order))).all()) == 1
    # boshqa kalit bilan — narx bir marta ishlatiladi
    r3 = await client.post(f"{API}/orders", json=body, headers={**h, "Idempotency-Key": "other-key-12"})
    assert r3.json()["code"] == "QUOTE_EXPIRED"
    # kalitsiz — 422
    assert (await client.post(f"{API}/orders", json=body, headers=h)).status_code == 422


async def test_rules_must_be_accepted(client, emp, ids):
    cats, district = ids
    _, h = emp
    q = (await client.post(f"{API}/orders/quote", json=order_body(cats, district), headers=h)).json()
    r = await client.post(
        f"{API}/orders",
        json={"quote_id": q["quote_id"], "accept_rules": False},
        headers={**h, "Idempotency-Key": "k-00000001"},
    )
    assert r.json()["code"] == "RULES_NOT_ACCEPTED"


@pytest.mark.parametrize(
    "patch,code",
    [
        ({"workers": 5}, "FIRST_ORDER_LIMIT"),
        ({"start_time": "00:00", "date": "2020-01-01"}, "START_TOO_SOON"),
        ({"date": "2099-01-01"}, "START_TOO_FAR"),
        ({"description": "Qarz undirish uchun odam kerak"}, "PROHIBITED_CONTENT"),
        ({"district_id": 99999}, "INVALID_DISTRICT"),
        ({"duration": None}, "DURATION_REQUIRED"),
        ({"payment_mode": "online"}, "PAYMENT_MODE_UNAVAILABLE"),
    ],
)
async def test_quote_validation(client, emp, ids, patch, code):
    cats, district = ids
    _, h = emp
    r = await client.post(f"{API}/orders/quote", json=order_body(cats, district, **patch), headers=h)
    assert r.status_code == 422 and r.json()["code"] == code, r.text


async def test_wrong_specialization_and_no_price(client, emp, ids):
    cats, district = ids
    _, h = emp
    cargo_spec = cats["cargo"]["specializations"][0]["id"]
    r = await client.post(
        f"{API}/orders/quote", headers=h, json=order_body(cats, district, specialization_id=cargo_spec)
    )
    assert r.json()["code"] == "INVALID_SPECIALIZATION"
    clean = cats["cleaning"]
    r = await client.post(
        f"{API}/orders/quote",
        headers=h,
        json=order_body(
            cats,
            district,
            category_id=clean["id"],
            specialization_id=clean["specializations"][0]["id"],
            duration=None,
            volume=40,
        ),
    )
    assert r.json()["code"] == "PRICE_NOT_CONFIGURED"  # uy xizmatlari narxini admin kiritadi


async def test_admin_price_then_cleaning_order(client, emp, ids, login, redis, db):
    cats, district = ids
    _, h = emp
    await redis.delete("otp:cooldown:+998908888888")
    admin, ah = await login("+998908888888")
    db.add(UserRole(user_id=admin["user"]["id"], role="admin"))
    await db.commit()
    clean = cats["cleaning"]
    assert (
        await client.post(
            f"{API}/admin/prices", headers=h, json={"category_id": clean["id"], "unit": "m2", "base": 5000}
        )
    ).status_code == 403
    r = await client.post(
        f"{API}/admin/prices",
        headers=ah,
        json={"category_id": clean["id"], "unit": "m2", "base": 5000, "min_order_amount": 200_000},
    )
    assert r.status_code == 201 and r.json()["min_price"] == 3750 and r.json()["max_price"] == 10_000

    body = order_body(
        cats,
        district,
        category_id=clean["id"],
        specialization_id=clean["specializations"][0]["id"],
        duration=None,
        volume=60,
        workers=2,
    )
    quote, o = await place(client, h, body)
    assert quote["price"]["unit"] == "m2" and quote["price"]["subtotal"] == 300_000
    assert o.json()["volume"] == "60" and o.json()["duration"] is None

    # narx o'zgarsa, eski buyurtma o'zgarmaydi
    await client.post(f"{API}/admin/prices", headers=ah, json={"category_id": clean["id"], "unit": "m2", "base": 8000})
    again = (await client.get(f"{API}/orders/{o.json()['id']}", headers=h)).json()
    assert again["price"]["subtotal"] == 300_000
    prices = (await client.get(f"{API}/admin/prices", headers=ah)).json()
    assert next(p for p in prices if p["category_id"] == clean["id"])["base"] == 8000


async def test_new_employer_big_order_needs_approval(client, emp, ids, db, login, redis):
    cats, district = ids
    uid, h = emp
    _, r = await place(client, h, order_body(cats, district, workers=2), key="first-order-1")
    assert r.status_code == 201
    _, r = await place(client, h, order_body(cats, district, workers=12), key="second-order")
    assert r.json()["status"] == "pending_approval"

    await redis.delete("otp:cooldown:+998908888888")
    admin, ah = await login("+998908888888")
    db.add(UserRole(user_id=admin["user"]["id"], role="admin"))
    await db.commit()
    r2 = await client.post(f"{API}/admin/orders/{r.json()['id']}/approve", headers=ah)
    assert r2.json()["status"] == "matching"


async def test_list_get_cancel_repeat(client, emp, ids, login, redis):
    cats, district = ids
    _, h = emp
    _, r = await place(client, h, order_body(cats, district))
    oid = r.json()["id"]
    assert [o["id"] for o in (await client.get(f"{API}/orders", headers=h)).json()] == [oid]

    # boshqa foydalanuvchi ko'rolmaydi
    await redis.delete("otp:cooldown:+998971111111")
    _, other = await login("+998971111111")
    assert (await client.get(f"{API}/orders/{oid}", headers=other)).status_code == 404

    r = await client.post(f"{API}/orders/{oid}/cancel", json={"reason": "Reja o'zgardi"}, headers=h)
    assert r.json()["status"] == "cancelled" and all(a["status"] == "cancelled" for a in r.json()["assignments"])
    assert (await client.post(f"{API}/orders/{oid}/cancel", json={}, headers=h)).status_code == 409

    day_after = (datetime.now(TASHKENT) + timedelta(days=2)).date().isoformat()
    q = (await client.post(f"{API}/orders/{oid}/repeat", json={"date": day_after}, headers=h)).json()
    assert q["price"]["employer_total"] == 450_000 and q["quote_id"]


async def test_employer_role_required(client, login):
    _, h = await login()
    r = await client.post(f"{API}/orders/quote", json={}, headers=h)
    assert r.status_code == 422  # sxema
    cats_resp = await client.get(f"{API}/catalog/categories")
    c = cats_resp.json()[0]
    district = (await client.get(f"{API}/catalog/districts")).json()[0]["id"]
    r = await client.post(f"{API}/orders/quote", json=order_body({"construction": c}, district), headers=h)
    assert r.status_code == 403 and r.json()["code"] == "NOT_AN_EMPLOYER"
