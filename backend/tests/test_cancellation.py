# ruff: noqa: F811  — `emp` fixture test_matching dan import qilinadi
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from workly.domain.cancellation import CancelTier, employer_terms, shrink_price, worker_terms
from workly.infrastructure.db.models import EmployerProfile, Order, ReliabilityEvent, WorkerProfile

from .test_matching import create_order, emp, headers_for, make_worker, offers_of, tick  # noqa: F401
from .test_workday import assigned, checkin

API = "/api/v1"
NOW = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)


# ---------------- sof qoidalar ----------------
def test_employer_terms():
    kw = dict(has_workers=True, arrived=False, order_total=300_000, first_day_total=150_000)
    assert employer_terms(NOW + timedelta(hours=30), NOW, **kw).tier == CancelTier.FREE
    t = employer_terms(NOW + timedelta(hours=10), NOW, **kw)
    assert (t.tier, t.percent, t.amount, t.reliability, t.charged) == (CancelTier.H6_24, 20, 60_000, -5, False)
    t = employer_terms(NOW + timedelta(hours=2), NOW, **kw)
    assert (t.percent, t.amount, t.reliability) == (50, 150_000, -10)
    t = employer_terms(NOW - timedelta(hours=1), NOW, **{**kw, "arrived": True})
    assert (t.tier, t.amount) == (CancelTier.AFTER_ARRIVAL, 150_000)
    assert employer_terms(NOW, NOW, **{**kw, "has_workers": False}).amount == 0


def test_worker_terms_and_shrink():
    assert worker_terms(NOW + timedelta(hours=25), NOW, 150_000).reliability == 0
    assert worker_terms(NOW + timedelta(hours=7), NOW, 150_000).reliability == -5
    t = worker_terms(NOW + timedelta(hours=1), NOW, 150_000)
    assert (t.percent, t.amount, t.reliability) == (20, 30_000, -10)
    price = {
        "worker_price": 150_000,
        "days": 1,
        "workers": 3,
        "subtotal": 450_000,
        "service_fee": 0,
        "employer_total": 450_000,
    }
    small = shrink_price(price, 2)
    assert (small["workers"], small["employer_total"], small["original"]["workers"]) == (2, 300_000, 3)
    assert shrink_price(small, 1)["employer_total"] == 150_000  # har doim asl narxdan


async def set_start(db, order_id, delta):
    db.expire_all()
    order = await db.get(Order, order_id)
    order.starts_at = datetime.now(UTC) + delta
    await db.commit()


# ---------------- employer bekor qiladi ----------------
async def test_employer_cancel_with_assigned_worker(client, emp, db, redis, sms, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    await set_start(db, order_id, timedelta(hours=30))
    p = (await client.get(f"{API}/orders/{order_id}/cancel-preview", headers=eh)).json()
    assert p == {"tier": "free", "percent": 0, "amount": 0, "reliability": 0, "charged": False}

    await set_start(db, order_id, timedelta(hours=3))
    p = (await client.get(f"{API}/orders/{order_id}/cancel-preview", headers=eh)).json()
    assert (p["tier"], p["percent"], p["amount"], p["reliability"]) == ("lt6", 50, 75_000, -10)
    assert (await client.get(f"{API}/orders/{order_id}/cancel-preview", headers=wh)).status_code == 404

    r = await client.post(f"{API}/orders/{order_id}/cancel", json={"reason": "Reja o'zgardi"}, headers=eh)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cancelled" and body["assignments"][0]["status"] == "cancelled"
    assert ("workday_event", aid, "order_cancelled") in notifier.calls
    employer = await db.get(EmployerProfile, body_employer_id(emp))
    await db.refresh(employer)
    assert employer.reliability == 90
    again = await client.post(f"{API}/orders/{order_id}/cancel", json={}, headers=eh)
    assert again.json()["code"] == "INVALID_STATE"


def body_employer_id(emp):
    return emp[0]


async def test_employer_cancel_after_arrival(client, emp, db, redis, sms):
    aid, order_id, _, wh, eh = await assigned(client, emp, db, redis, sms)
    await checkin(client, aid, wh)
    p = (await client.get(f"{API}/orders/{order_id}/cancel-preview", headers=eh)).json()
    assert (p["tier"], p["percent"], p["amount"]) == ("after_arrival", 100, 150_000)
    r = await client.post(f"{API}/orders/{order_id}/cancel", json={}, headers=eh)
    assert r.json()["status"] == "cancelled"


# ---------------- ishchi bekor qiladi ----------------
async def test_worker_cancel_reopens_slot(client, emp, db, redis, sms, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    await set_start(db, order_id, timedelta(hours=3))
    p = (await client.get(f"{API}/assignments/{aid}/cancel-preview", headers=wh)).json()
    assert (p["tier"], p["amount"], p["reliability"]) == ("lt6", 30_000, -10)

    r = await client.post(f"{API}/assignments/{aid}/cancel", json={"reason": "Kasal bo'lib qoldim"}, headers=wh)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    profile = await db.get(WorkerProfile, wid)
    await db.refresh(profile)
    assert profile.reliability == 90
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert [a["status"] for a in order["assignments"]] == ["cancelled", "open"]
    assert order["status"] == "matching"
    assert ("order_event", order_id, "worker_cancelled") in notifier.calls


async def test_worker_cancel_rules(client, emp, db, redis, sms, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    await set_start(db, order_id, timedelta(minutes=-5))
    r = await client.post(f"{API}/assignments/{aid}/cancel", json={}, headers=wh)
    assert r.json()["code"] == "CANCEL_TOO_LATE"
    assert (await client.post(f"{API}/assignments/{aid}/cancel", json={}, headers=eh)).status_code == 404

    # Oyiga 3-bepul bekor — ogohlantirish
    await set_start(db, order_id, timedelta(hours=30))
    for _ in range(2):
        db.add(ReliabilityEvent(user_id=wid, role="worker", delta=0, reason="cancel_free"))
    await db.commit()
    r = await client.post(f"{API}/assignments/{aid}/cancel", json={}, headers=wh)
    assert r.status_code == 200
    assert ("workday_event", aid, "cancel_warning") in notifier.calls


# ---------------- sevimlilar va bloklar ----------------
async def test_favorites_get_separate_first_wave(client, emp, db, redis, sms, notifier):
    aid, order_id, fav, wh, eh = await assigned(client, emp, db, redis, sms)
    stranger = await make_worker(db, 9)
    # Men bilan ishlamagan ishchini sevimli qilib bo'lmaydi
    assert (await client.put(f"{API}/employer/favorites/{stranger}", headers=eh)).status_code == 404
    assert (await client.put(f"{API}/employer/favorites/{fav}", headers=eh)).status_code == 204
    known = (await client.get(f"{API}/employer/workers", headers=eh)).json()
    assert [(w["worker_id"], w["favorite"], w["jobs"]) for w in known] == [(fav, True, 1)]
    other = await make_worker(db, 2)

    order2 = await create_order(client, eh, db, start_in=timedelta(days=2), key="k-000002")
    offers = await offers_of(db, order2)
    assert [(o.worker_id, o.wave) for o in offers] == [(fav, 1)]  # faqat sevimli
    order = await db.get(Order, order2)
    await db.refresh(order)
    assert order.waves_sent == 0 and order.favorites_sent_at is not None  # limitga kirmaydi

    # Sevimli javob bermadi — oddiy to'lqin qolganlarga
    await tick(db, redis, notifier, datetime.now(UTC) + timedelta(minutes=11))
    offers = await offers_of(db, order2)
    assert {o.worker_id for o in offers if o.status == "sent"} == {other, stranger}
    detail = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert detail["assignments"][0]["favorite"] is True


async def test_blocked_worker_gets_no_offers(client, emp, db, redis, sms):
    aid, order_id, bad, wh, eh = await assigned(client, emp, db, redis, sms)
    await client.put(f"{API}/employer/favorites/{bad}", headers=eh)
    assert (await client.put(f"{API}/employer/blocks/{bad}", headers=eh)).status_code == 204
    known = (await client.get(f"{API}/employer/workers", headers=eh)).json()
    assert (known[0]["favorite"], known[0]["blocked"]) == (False, True)  # blok sevimlini olib tashlaydi
    good = await make_worker(db, 2)
    order2 = await create_order(client, eh, db, start_in=timedelta(days=2), key="k-000002")
    assert {o.worker_id for o in await offers_of(db, order2)} == {good}
    # Lentada ham ko'rinmaydi
    feed = (await client.get(f"{API}/jobs/open", headers=wh)).json()
    assert order2 not in [j["order_id"] for j in feed]

    assert (await client.delete(f"{API}/employer/blocks/{bad}", headers=eh)).status_code == 204
    order3 = await create_order(client, eh, db, start_in=timedelta(days=3), key="k-000003")
    assert bad in {o.worker_id for o in await offers_of(db, order3)}


# ---------------- T−60 qisman to'lgan buyurtma ----------------
async def partial_order(client, emp, db, redis, sms):
    _, eh = emp
    wid = await make_worker(db, 1)
    order_id = await create_order(client, eh, db, workers=2)
    offer = (await offers_of(db, order_id))[0]
    wh = await headers_for(client, db, wid, redis, sms)
    assert (await client.post(f"{API}/offers/{offer.id}/accept", headers=wh)).status_code == 200
    await set_start(db, order_id, timedelta(minutes=50))
    return order_id, eh


async def test_partial_start_with_found(client, emp, db, redis, sms, notifier):
    order_id, eh = await partial_order(client, emp, db, redis, sms)
    r = await client.post(f"{API}/orders/{order_id}/partial", json={"start": True}, headers=eh)
    assert r.json()["code"] == "PARTIAL_NOT_ASKED"

    stats = await tick(db, redis, notifier, datetime.now(UTC))
    assert stats["partial"] == 1 and ("order_event", order_id, "partial_decision") in notifier.calls
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert order["status"] == "partially_assigned" and order["partial_asked_at"]

    r = await client.post(f"{API}/orders/{order_id}/partial", json={"start": True}, headers=eh)
    body = r.json()
    assert body["status"] == "assigned" and body["partial_decision"] == "start"
    assert body["workers"] == 1 and body["price"]["employer_total"] == 150_000
    assert [a["status"] for a in body["assignments"]] == ["assigned", "cancelled"]
    await tick(db, redis, notifier, datetime.now(UTC) + timedelta(minutes=1))
    assert notifier.calls.count(("order_event", order_id, "partial_decision")) == 1  # qayta so'ralmaydi


async def test_partial_wait_then_closed_at_start(client, emp, db, redis, sms, notifier):
    order_id, eh = await partial_order(client, emp, db, redis, sms)
    await tick(db, redis, notifier, datetime.now(UTC))
    r = await client.post(f"{API}/orders/{order_id}/partial", json={"start": False}, headers=eh)
    assert r.json()["partial_decision"] == "wait" and r.json()["status"] == "partially_assigned"

    await tick(db, redis, notifier, datetime.now(UTC) + timedelta(minutes=51))
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert order["status"] == "assigned" and order["workers"] == 1
    assert [a["status"] for a in order["assignments"]] == ["assigned", "cancelled"]


@pytest.mark.parametrize("path", ["favorites", "blocks"])
async def test_relations_require_employer_link(client, emp, db, path):
    _, eh = emp
    wid = await make_worker(db, 5)
    assert (await client.put(f"{API}/employer/{path}/{wid}", headers=eh)).status_code == 404
    assert (await db.scalars(select(ReliabilityEvent))).all() == []
