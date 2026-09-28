# ruff: noqa: F811  — `emp` fixture test_matching dan import qilinadi
from datetime import timedelta

import pytest

from workly.infrastructure.db.models import EmployerProfile, UserRole

from .test_cancellation import set_start
from .test_matching import create_order, emp, headers_for, make_worker, offers_of  # noqa: F401
from .test_workday import assigned, checkin

API = "/api/v1"


@pytest.fixture
async def admin(client, login, redis, db, elevate):
    await redis.delete("otp:cooldown:+998908888888")
    body, h = await login("+998908888888")
    db.add(UserRole(user_id=body["user"]["id"], role="admin"))
    await db.commit()
    return body["user"]["id"], await elevate(body["user"]["id"], h)


async def test_call_queue(client, emp, db, redis, sms, admin, moderator):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    _, ah = admin
    _, mh = moderator
    board = (await client.get(f"{API}/admin/ops/board", headers=ah)).json()
    assert board["call_queue"] == []

    await set_start(db, order_id, timedelta(minutes=-35))
    board = (await client.get(f"{API}/admin/ops/board", headers=mh)).json()  # moderator ham ko'radi
    item = board["call_queue"][0]
    assert (item["assignment_id"], item["worker_id"]) == (aid, wid)
    assert item["minutes_late"] >= 35 and item["worker_phone"] and item["employer_phone"]

    r = await client.post(f"{API}/admin/ops/calls/{aid}", json={"note": "Yo'lda, 10 daqiqada yetadi"}, headers=mh)
    assert r.status_code == 204
    assert (await client.get(f"{API}/admin/ops/board", headers=ah)).json()["call_queue"] == []
    # Moderatorga buyurtmalar va foydalanuvchilar yopiq (TZ 16)
    assert (await client.get(f"{API}/admin/orders", headers=mh)).status_code == 403
    assert (await client.get(f"{API}/admin/users?q=998", headers=mh)).status_code == 403
    # Oddiy token (TOTP'siz) — taxta ham yopiq
    assert (await client.get(f"{API}/admin/ops/board", headers=eh)).status_code == 403


async def test_resolve_dispute_confirm(client, emp, db, redis, sms, admin, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    employer_id, _ = emp
    _, ah = admin
    await checkin(client, aid, wh)
    await client.post(f"{API}/assignments/{aid}/finish", headers=wh)
    reason = "Ish sifatsiz bajarildi, devor egri chiqdi"
    await client.post(f"{API}/assignments/{aid}/confirm", json={"ok": False, "reason": reason}, headers=eh)

    board = (await client.get(f"{API}/admin/ops/board", headers=ah)).json()
    assert board["pending"]["disputes"] == 1 and board["problems"][0]["assignment_id"] == aid

    body = {"confirm": True, "reason": "qisqa"}
    r = await client.post(f"{API}/admin/assignments/{aid}/resolve", json=body, headers=ah)
    assert r.json()["code"] == "REASON_REQUIRED"
    body = {"confirm": True, "reason": "Rasmlar bo'yicha ish bajarilgan", "unfounded": "employer"}
    r = await client.post(f"{API}/admin/assignments/{aid}/resolve", json=body, headers=ah)
    assert r.status_code == 204
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert order["status"] == "completed" and order["assignments"][0]["status"] == "confirmed"
    db.expire_all()
    assert (await db.get(EmployerProfile, employer_id)).reliability == 90  # asossiz nizo −10
    assert ("workday_event", aid, "dispute_resolved") in notifier.calls
    r = await client.post(f"{API}/admin/assignments/{aid}/resolve", json=body, headers=ah)
    assert r.json()["code"] == "INVALID_STATE"


async def test_resolve_identity_dispute_reopens_slot(client, emp, db, redis, sms, admin):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    _, ah = admin
    await checkin(client, aid, wh)
    await client.post(f"{API}/assignments/{aid}/confirm-arrival", json={"same_person": False}, headers=eh)
    body = {"confirm": False, "reason": "Selfie va kelgan odam boshqa", "unfounded": None}
    assert (await client.post(f"{API}/admin/assignments/{aid}/resolve", json=body, headers=ah)).status_code == 204
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert [a["status"] for a in order["assignments"]] == ["cancelled", "open"]


async def test_orders_search_detail_cancel(client, emp, db, redis, sms, admin, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    employer_id, _ = emp
    _, ah = admin
    by_id = (await client.get(f"{API}/admin/orders?q=%23{order_id}", headers=ah)).json()
    assert [o["id"] for o in by_id] == [order_id]
    by_phone = (await client.get(f"{API}/admin/orders?q=905000001", headers=ah)).json()  # ishchi telefoni
    assert [o["id"] for o in by_phone] == [order_id]
    assert (await client.get(f"{API}/admin/orders?status=completed", headers=ah)).json() == []

    detail = (await client.get(f"{API}/admin/orders/{order_id}", headers=ah)).json()
    assert detail["employer_id"] == employer_id
    assert ("assignment", "open", "assigned") in [
        (t["object_type"], t["from_state"], t["to_state"]) for t in detail["timeline"]
    ]

    r = await client.post(f"{API}/admin/orders/{order_id}/cancel", json={"reason": "qisqa"}, headers=ah)
    assert r.json()["code"] == "REASON_REQUIRED"
    r = await client.post(
        f"{API}/admin/orders/{order_id}/cancel", json={"reason": "Firibgarlik shubhasi, tekshiruv"}, headers=ah
    )
    assert r.json()["status"] == "cancelled"
    assert ("workday_event", aid, "order_cancelled") in notifier.calls
    assert ("order_event", order_id, "cancelled_by_admin") in notifier.calls
    db.expire_all()
    profile = await db.get(EmployerProfile, employer_id)
    assert profile is None or profile.reliability == 100  # employerga jarima yo'q


async def test_manual_assign(client, emp, db, redis, sms, admin, notifier):
    _, eh = emp
    _, ah = admin
    order_id = await create_order(client, eh, db)  # hali ishchi yo'q — to'lqin bo'sh
    wid = await make_worker(db, 3)
    unverified = await make_worker(db, 4, verified=False)
    r = await client.post(f"{API}/admin/orders/{order_id}/assign", json={"worker_id": unverified}, headers=ah)
    assert r.json()["code"] == "WORKER_NOT_VERIFIED"
    r = await client.post(f"{API}/admin/orders/{order_id}/assign", json={"worker_id": wid}, headers=ah)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "assigned" and r.json()["assignments"][0]["worker_id"] == wid
    assert any(c[0] == "worker_assigned" for c in notifier.calls)


async def test_users_block_unblock(client, emp, db, redis, sms, admin):
    employer_id, eh = emp
    admin_id, ah = admin
    found = (await client.get(f"{API}/admin/users?q=971234567", headers=ah)).json()
    assert [u["id"] for u in found] == [employer_id] and "employer" in found[0]["roles"]

    r = await client.post(
        f"{API}/admin/users/{employer_id}/block", json={"reason": "Tashqarida to'lov isbotlandi"}, headers=ah
    )
    assert r.json()["status"] == "blocked"
    r = await client.get(f"{API}/me", headers=eh)
    assert r.status_code == 403 and r.json()["code"] == "USER_BLOCKED"
    r = await client.post(f"{API}/admin/users/{admin_id}/block", json={"reason": "O'zimni sinab ko'raman"}, headers=ah)
    assert r.json()["code"] == "SELF_BLOCK"

    r = await client.post(
        f"{API}/admin/users/{employer_id}/unblock", json={"reason": "Admin suhbatidan keyin"}, headers=ah
    )
    assert r.json()["status"] == "active"
    assert (await client.get(f"{API}/me", headers=eh)).status_code == 200
    history = (await client.get(f"{API}/admin/users/{employer_id}/history", headers=ah)).json()
    assert [h["action"] for h in history][:2] == ["user.unblock", "user.block"]
