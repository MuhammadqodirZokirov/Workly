# ruff: noqa: F811  — `emp` fixture test_matching dan import qilinadi
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from workly.application.workday import WorkdayService
from workly.domain.workday import RatingInput, bayes_rating, no_show_penalty
from workly.infrastructure.db.models import (
    Assignment,
    CheckIn,
    Offer,
    Order,
    ReliabilityEvent,
    Review,
    User,
    WorkerProfile,
)
from workly.workers.scheduler import tick_once

from .test_matching import CHILONZOR, create_order, emp, headers_for, make_worker, offers_of  # noqa: F401
from .test_worker import JPEG

API = "/api/v1"


# ---------------- sof qoidalar ----------------
def test_bayes_rating():
    assert bayes_rating([]) is None
    # 3 ta "prior" 4.5 + bitta 5 → (13.5 + 5) / 4
    assert bayes_rating([RatingInput(5, False)]) == pytest.approx(4.62, abs=0.01)
    low = [RatingInput(1, False)] * 20
    assert bayes_rating(low) < 2
    assert no_show_penalty(1)[0] == -20 and no_show_penalty(2)[1] == "suspend_3d" and no_show_penalty(3)[1] == "block"


# ---------------- yordamchilar ----------------
async def assigned(client, emp, db, redis, sms, *, start_in=timedelta(minutes=10), n=1):
    """Tasdiqlangan ishchi buyurtmani qabul qilgan; boshlanish vaqti start_in ga suriladi."""
    wid = await make_worker(db, n)
    _, eh = emp
    order_id = await create_order(client, eh, db, key=f"k-00000{n}")
    offer = (await offers_of(db, order_id))[0]
    wh = await headers_for(client, db, wid, redis, sms)
    r = await client.post(f"{API}/offers/{offer.id}/accept", headers=wh)
    assert r.status_code == 200, r.text
    order = await db.get(Order, order_id)
    order.starts_at = datetime.now(UTC) + start_in
    await db.commit()
    return r.json()["assignment_id"], order_id, wid, wh, eh


async def checkin(client, aid, wh, lat=CHILONZOR[0], lon=CHILONZOR[1], accuracy=20.0, file=JPEG):
    return await client.post(
        f"{API}/assignments/{aid}/checkin",
        headers=wh,
        data={"lat": lat, "lon": lon, "accuracy": accuracy},
        files={"selfie": ("s.jpg", file, "image/jpeg")},
    )


async def state(db, aid) -> Assignment:
    db.expire_all()
    return await db.get(Assignment, aid)


# ---------------- check-in ----------------
async def test_checkin_ok(client, emp, db, redis, sms, notifier, settings):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    r = await checkin(client, aid, wh, lat=CHILONZOR[0] + 0.001)  # ~110 m
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "arrived" and r.json()["arrived_at"]
    c = await db.scalar(select(CheckIn).where(CheckIn.assignment_id == aid))
    assert c.accepted and 100 < c.distance_m < 130 and c.selfie_key
    assert ("workday_event", aid, "worker_arrived") in notifier.calls
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert order["status"] == "in_progress"


@pytest.mark.parametrize(
    "kw,code",
    [
        ({"lat": CHILONZOR[0] + 0.01}, "GPS_TOO_FAR"),  # ~1.1 km
        ({"accuracy": 500.0}, "GPS_INACCURATE"),
    ],
)
async def test_checkin_gps_rejected_but_logged(client, emp, db, redis, sms, kw, code):
    aid, *_, wh, _ = await assigned(client, emp, db, redis, sms)
    r = await checkin(client, aid, wh, **kw)
    assert r.status_code == 422 and r.json()["code"] == code
    attempts = (await db.scalars(select(CheckIn).where(CheckIn.assignment_id == aid))).all()
    assert len(attempts) == 1 and not attempts[0].accepted and attempts[0].selfie_key is None  # dalil, selfie'siz
    assert (await state(db, aid)).status == "assigned"


async def test_checkin_window_and_owner(client, emp, db, redis, sms):
    aid, *_, wh, eh = await assigned(client, emp, db, redis, sms, start_in=timedelta(hours=2))
    assert (await checkin(client, aid, wh)).json()["code"] == "CHECKIN_TOO_EARLY"
    assert (await checkin(client, aid, eh)).status_code == 404  # boshqa foydalanuvchi


async def test_employer_manual_and_identity(client, emp, db, redis, sms, notifier):
    aid, _, _, wh, eh = await assigned(client, emp, db, redis, sms)
    # GPS ishlamasa — employer qo'lda tasdiqlaydi
    r = await client.post(f"{API}/assignments/{aid}/confirm-arrival", json={"same_person": True}, headers=eh)
    assert r.json()["status"] == "working"

    aid2, _, _, wh2, _ = await assigned(client, emp, db, redis, sms, n=2)
    await checkin(client, aid2, wh2)
    r = await client.post(f"{API}/assignments/{aid2}/confirm-arrival", json={"same_person": False}, headers=eh)
    assert r.json()["status"] == "disputed" and r.json()["problem"] == "identity_mismatch"
    assert ("workday_event", aid2, "problem") in notifier.calls


# ---------------- yakunlash ----------------
async def test_full_day_confirm_and_reviews(client, emp, db, redis, sms, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    profile = await db.get(WorkerProfile, wid)
    profile.reliability = 90
    await db.commit()
    await checkin(client, aid, wh)
    await client.post(f"{API}/assignments/{aid}/confirm-arrival", json={"same_person": True}, headers=eh)
    assert (await client.post(f"{API}/assignments/{aid}/finish", headers=wh)).json()["status"] == "finished"

    r = await client.post(f"{API}/assignments/{aid}/confirm", json={"ok": False, "reason": "yomon"}, headers=eh)
    assert r.json()["code"] == "REASON_REQUIRED"
    r = await client.post(f"{API}/assignments/{aid}/confirm", json={"ok": True}, headers=eh)
    assert r.json()["status"] == "confirmed" and r.json()["auto_confirmed"] is False
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert order["status"] == "completed"
    await db.refresh(profile)
    assert profile.reliability == 92  # +2 muammosiz ish

    r = await client.post(f"{API}/assignments/{aid}/cash-received", json={"amount": 150_000}, headers=wh)
    assert r.json()["cash_received"] == 150_000 and r.json()["problem"] is None

    # Baholar: bittasi baholaganda qarshi tomon ko'rmaydi
    r = await client.post(
        f"{API}/assignments/{aid}/review",
        headers=eh,
        json={"rating": 5, "tags": ["on_time", "quality"], "comment": "Zo'r ishladi"},
    )
    assert r.status_code == 201
    other = (await client.get(f"{API}/assignments/{aid}/reviews", headers=wh)).json()
    assert other == {"reviewed_by_me": False, "visible": []}
    bad = await client.post(f"{API}/assignments/{aid}/review", headers=wh, json={"rating": 4, "tags": ["quality"]})
    assert bad.json()["code"] == "INVALID_TAG"  # ishchi employerga boshqa teglar qo'yadi
    await client.post(f"{API}/assignments/{aid}/review", headers=wh, json={"rating": 4, "tags": ["paid_on_time"]})
    both = (await client.get(f"{API}/assignments/{aid}/reviews", headers=wh)).json()
    assert len(both["visible"]) == 2 and both["reviewed_by_me"]
    dup = await client.post(f"{API}/assignments/{aid}/review", headers=wh, json={"rating": 4})
    assert dup.json()["code"] == "ALREADY_REVIEWED"

    # Rezyume endi haqiqiy statistika ko'rsatadi
    resume = (await client.get(f"{API}/workers/{wid}", headers=eh)).json()
    assert resume["stats"]["completed_jobs"] == 1 and resume["stats"]["reviews_count"] == 1
    assert resume["stats"]["rating"] == pytest.approx(4.62, abs=0.01) and resume["is_new"] is True
    assert resume["recent_reviews"][0]["comment"] == "Zo'r ishladi"


async def test_problem_and_cash_short(client, emp, db, redis, sms, notifier):
    aid, _, _, wh, eh = await assigned(client, emp, db, redis, sms)
    await checkin(client, aid, wh)
    await client.post(f"{API}/assignments/{aid}/finish", headers=wh)
    r = await client.post(f"{API}/assignments/{aid}/cash-received", json={"amount": 100_000}, headers=wh)
    assert r.json()["problem"].startswith("cash_short")
    r = await client.post(
        f"{API}/assignments/{aid}/confirm",
        headers=eh,
        json={"ok": False, "reason": "Ish oxirigacha bajarilmadi, devor chala qoldi"},
    )
    assert r.json()["status"] == "disputed"
    assert ("workday_event", aid, "problem") in notifier.calls


# ---------------- scheduler: kechikish, kelmaslik, avtomatik ----------------
async def test_late_reminders_and_no_show(client, emp, db, redis, sms):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    t = (await db.get(Order, order_id)).starts_at.replace(tzinfo=UTC)

    async def tick_at(delta):
        svc = WorkdayService(db, now=t + delta)
        stats = await svc.tick()
        await db.commit()
        return svc, stats

    svc, _ = await tick_at(timedelta(minutes=16))
    assert ("workday_event", (aid, "late_15")) in svc.outbox
    svc, _ = await tick_at(timedelta(minutes=17))
    assert not any(k == (aid, "late_15") for _, k in svc.outbox)  # qayta yuborilmaydi
    svc, _ = await tick_at(timedelta(minutes=31))
    assert ("workday_event", (aid, "late_30")) in svc.outbox

    # T+30 dan keyin employer almashtira oladi — lekin avval T+60 ni tekshiramiz
    svc, stats = await tick_at(timedelta(minutes=61))
    assert stats["no_show"] == 1
    a = await state(db, aid)
    assert a.status == "no_show"
    profile = await db.get(WorkerProfile, wid)
    await db.refresh(profile)
    assert profile.reliability == 80
    order = await db.get(Order, order_id)
    await db.refresh(order, attribute_names=["assignments"])
    assert [x.status for x in order.assignments] == ["no_show", "open"] and order.waves_sent == 0
    assert ("replacement_wave", (order_id,)) in svc.outbox


async def test_repeat_no_shows_suspend_then_block(db):
    wid = await make_worker(db, 1)
    now = datetime.now(UTC)
    for _ in range(1):
        db.add(ReliabilityEvent(user_id=wid, role="worker", delta=-20, reason="no_show", created_at=now))
    await db.commit()
    order = Order(
        employer_id=wid,
        category_id=1,
        specialization_id=1,
        workers_count=1,
        starts_at=now,
        lat=CHILONZOR[0],
        lon=CHILONZOR[1],
        district_id=1,
        address_text="x",
        price={"worker_price": 1},
        status="assigned",
    )
    order.assignments = [Assignment(slot_no=1, worker_id=wid, status="assigned")]
    db.add(order)
    await db.commit()
    svc = WorkdayService(db, now=now + timedelta(minutes=61))
    await svc.tick()
    await db.commit()
    profile = await db.get(WorkerProfile, wid)
    await db.refresh(profile)
    assert profile.suspended_until is not None  # 2-marta — 3 kun to'xtatish

    db.add(ReliabilityEvent(user_id=wid, role="worker", delta=-20, reason="no_show", created_at=now))
    order2 = Order(
        employer_id=wid,
        category_id=1,
        specialization_id=1,
        workers_count=1,
        starts_at=now,
        lat=CHILONZOR[0],
        lon=CHILONZOR[1],
        district_id=1,
        address_text="x",
        price={"worker_price": 1},
        status="assigned",
    )
    order2.assignments = [Assignment(slot_no=1, worker_id=wid, status="assigned")]
    db.add(order2)
    await db.commit()
    await WorkdayService(db, now=now + timedelta(minutes=61)).tick()
    await db.commit()
    user = await db.get(User, wid)
    await db.refresh(user)
    assert user.status == "blocked"  # 90 kunda 3-marta


async def test_replacement_wave_after_no_show(client, emp, db, redis, sms, maker, notifier):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    backup = await make_worker(db, 7, available=True)  # "Hozir bo'shman" — shoshilinch almashtirish
    order = await db.get(Order, order_id)
    order.starts_at = datetime.now(UTC) - timedelta(minutes=61)
    await db.commit()
    await tick_once(maker, redis, notifier)
    offers = await offers_of(db, order_id)
    assert backup in {o.worker_id for o in offers if o.status == "sent"}
    new_offer = next(o for o in offers if o.worker_id == backup)
    bh = await headers_for(client, db, backup, redis, sms)
    r = await client.post(f"{API}/offers/{new_offer.id}/accept", headers=bh)
    assert r.status_code == 200, r.text  # boshlangan buyurtmaga ham qabul qilinadi


async def test_auto_arrival_confirm_and_reviews(client, emp, db, redis, sms):
    aid, order_id, wid, wh, eh = await assigned(client, emp, db, redis, sms)
    await checkin(client, aid, wh)
    a = await state(db, aid)
    arrived = a.arrived_at.replace(tzinfo=UTC)

    await WorkdayService(db, now=arrived + timedelta(minutes=16)).tick()
    await db.commit()
    assert (await state(db, aid)).status == "working"  # employer 15 daqiqada javob bermadi

    await client.post(f"{API}/assignments/{aid}/finish", headers=wh)
    finished = (await state(db, aid)).finished_at.replace(tzinfo=UTC)
    svc = WorkdayService(db, now=finished + timedelta(hours=21))
    await svc.tick()
    await db.commit()
    assert ("workday_event", (aid, "confirm_reminder")) in svc.outbox
    await WorkdayService(db, now=finished + timedelta(hours=25)).tick()
    await db.commit()
    a = await state(db, aid)
    assert a.status == "confirmed" and a.auto_confirmed

    # 48 soatda baho yo'q — ikki tomonga avtomatik baho (yangi foydalanuvchida 4.5)
    await WorkdayService(db, now=a.confirmed_at.replace(tzinfo=UTC) + timedelta(hours=49)).tick()
    await db.commit()
    reviews = (await db.scalars(select(Review).where(Review.assignment_id == aid))).all()
    assert len(reviews) == 2 and all(r.is_auto and r.rating == 4.5 and r.visible_at for r in reviews)
    resume = (await client.get(f"{API}/workers/{wid}", headers=eh)).json()
    assert resume["stats"]["reviews_count"] == 0 and resume["is_new"]  # avtomatik baho sanalmaydi


async def test_employer_replace_after_30_min(client, emp, db, redis, sms):
    aid, order_id, *_, eh = await assigned(client, emp, db, redis, sms)
    r = await client.post(f"{API}/assignments/{aid}/replace", headers=eh)
    assert r.json()["code"] == "REPLACE_NOT_ALLOWED"
    order = await db.get(Order, order_id)
    order.starts_at = datetime.now(UTC) - timedelta(minutes=31)
    await db.commit()
    r = await client.post(f"{API}/assignments/{aid}/replace", headers=eh)
    assert r.json()["status"] == "replaced"
    order = (await client.get(f"{API}/orders/{order_id}", headers=eh)).json()
    assert [a["status"] for a in order["assignments"]] == ["replaced", "open"]


async def test_selfie_purged_after_30_days(client, emp, db, redis, sms, settings):
    aid, _, _, wh, _ = await assigned(client, emp, db, redis, sms)
    await checkin(client, aid, wh)
    c = await db.scalar(select(CheckIn).where(CheckIn.assignment_id == aid))
    svc = WorkdayService(db, now=c.created_at.replace(tzinfo=UTC) + timedelta(days=31))
    stats = await svc.tick()
    await db.commit()
    assert stats["selfies_purged"] == 1 and svc.files_to_delete
    assert await db.scalar(select(CheckIn.selfie_key).where(CheckIn.id == c.id)) is None


async def test_offers_untouched(db):
    # workday tick takliflarga tegmaydi
    assert (await db.scalars(select(Offer))).all() == []
