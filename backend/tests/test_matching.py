import datetime as dt
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from workly.application.matching import MatchingService
from workly.domain.matching import WorkerSignals, compose_wave, fits_schedule, haversine_km, score, wave_size
from workly.infrastructure.db.models import (
    Assignment,
    Category,
    District,
    Offer,
    Order,
    Specialization,
    User,
    UserRole,
    WorkerAvailability,
    WorkerDistrict,
    WorkerProfile,
    WorkerSkill,
    WorkerSpecialization,
)
from workly.interfaces.bot.factory import create_dispatcher

from .conftest import BOT_TOKEN
from .test_bot import FakeSession

API = "/api/v1"
TASHKENT = ZoneInfo("Asia/Tashkent")
CHILONZOR = (41.2856, 69.2034)
FAR_AWAY = (41.55, 69.70)  # ~50 km


# ---------------- sof funksiyalar ----------------
def sig(wid, **kw):
    base = dict(
        worker_id=wid,
        rating=None,
        reviews_count=10,
        completion_rate=None,
        avg_response_min=None,
        distance_km=5.0,
        experience="none",
        days_since_last_job=None,
    )
    base.update(kw)
    return WorkerSignals(**base)


def test_score_formula():
    # R=0.9 (yangi), C=0.5, T=0.5, D=0.5, E=1, A=1 → 0.27 + 0.1 + 0.075 + 0.075 + 0.1 + 0.1
    assert score(sig(1, experience="5_plus", days_since_last_job=3)) == pytest.approx(0.72)
    best = score(
        sig(
            1,
            rating=5.0,
            completion_rate=1.0,
            avg_response_min=0,
            distance_km=0,
            experience="5_plus",
            days_since_last_job=1,
        )
    )
    assert best == pytest.approx(1.0)


def test_wave_size_and_cold_start():
    assert (wave_size(1), wave_size(3), wave_size(10)) == (5, 9, 15)
    experienced = [sig(i) for i in range(1, 10)]
    new = sig(99, reviews_count=0)
    wave = compose_wave([*experienced, new], 5)
    assert [w.worker_id for w in wave] == [1, 2, 3, 4, 99]  # 5-o'rin — yangi ishchiga


def test_schedule_and_distance():
    slots = [(0, time(8), time(18))]
    assert fits_schedule(slots, 0, time(8), 8) and not fits_schedule(slots, 0, time(12), 8)
    assert not fits_schedule(slots, 1, time(8), 4)
    assert fits_schedule([], 3, time(23), 8)  # jadval yo'q — istalgan vaqt
    assert 49 < haversine_km(*CHILONZOR, *FAR_AWAY) < 55


# ---------------- yordamchilar ----------------
async def refs(db):
    cat = await db.scalar(select(Category).where(Category.code == "construction"))
    spec = await db.scalar(
        select(Specialization).where(Specialization.category_id == cat.id, Specialization.code == "general")
    )
    other = await db.scalar(select(Specialization).where(Specialization.code == "loader"))
    districts = list(await db.scalars(select(District).order_by(District.sort_order)))
    return cat, spec, other, districts


async def make_worker(
    db, n, *, spec=None, district=None, home=None, verified=True, slots=(), available=False, experience="1_2"
):
    _, general, _, districts = await refs(db)
    spec = spec or general
    user = User(
        phone=f"+99890500{n:04d}", phone_verified_at=datetime.now(UTC), full_name=f"W{n} Ali", telegram_id=70000 + n
    )
    user.roles.append(UserRole(role="worker"))
    db.add(user)
    await db.flush()
    p = WorkerProfile(
        user_id=user.id,
        first_name=f"Ishchi{n}",
        last_name="Karimov",
        birth_date=dt.date(1995, 1, 1),
        gender="male",
        verification_status="verified" if verified else "pending",
        home_lat=home[0] if home else None,
        home_lon=home[1] if home else None,
        available_now_until=datetime.now(UTC) + timedelta(hours=8) if available else None,
    )
    p.skills = [WorkerSkill(category_id=spec.category_id, experience=experience)]
    p.specializations = [WorkerSpecialization(category_id=spec.category_id, specialization_id=spec.id)]
    p.districts = [WorkerDistrict(district_id=(district or districts[1]).id)]
    p.availability = [WorkerAvailability(weekday=d, start=s, end=e) for d, s, e in slots]
    db.add(p)
    await db.commit()
    return user.id


@pytest.fixture
async def emp(client, login, redis):
    await redis.delete("otp:cooldown:+998971234567")
    body, h = await login("+998971234567")
    await client.post(f"{API}/me/roles", json={"role": "employer"}, headers=h)
    return body["user"]["id"], h


async def create_order(client, h, db, *, workers=1, start_in=timedelta(days=1), at="08:00", key="k-000001"):
    _, general, _, districts = await refs(db)
    when = datetime.now(TASHKENT) + start_in
    start = at if start_in >= timedelta(days=1) else when.strftime("%H:%M")
    body = {
        "category_id": general.category_id,
        "specialization_id": general.id,
        "workers": workers,
        "date": when.date().isoformat(),
        "start_time": start,
        "duration": "day",
        "point": {"lat": CHILONZOR[0], "lon": CHILONZOR[1]},
        "district_id": districts[1].id,
        "address_text": "Chilonzor 9-kvartal, 12-uy",
        "landmark": "Maktab yonida",
    }
    q = await client.post(f"{API}/orders/quote", json=body, headers=h)
    assert q.status_code == 200, q.text
    r = await client.post(
        f"{API}/orders",
        json={"quote_id": q.json()["quote_id"], "accept_rules": True},
        headers={**h, "Idempotency-Key": key},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def offers_of(db, order_id):
    db.expire_all()
    return list(await db.scalars(select(Offer).where(Offer.order_id == order_id).order_by(Offer.id)))


async def headers_for(client, db, user_id, redis, sms):
    user = await db.get(User, user_id)
    await redis.delete(f"otp:cooldown:{user.phone}")
    await client.post(f"{API}/auth/otp/send", json={"phone": user.phone})
    r = await client.post(f"{API}/auth/otp/verify", json={"phone": user.phone, "code": sms.last_code()})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def tick(db, redis, notifier, now):
    svc = MatchingService(db, redis, notifier, now=now)
    stats = await svc.tick()
    await db.commit()
    await svc.flush_outbox()
    return stats


# ---------------- birinchi to'lqin ----------------
async def test_first_wave_eligibility(client, emp, db, notifier):
    _, _, loader, districts = await refs(db)
    in_district = await make_worker(db, 1)
    near_home = await make_worker(db, 2, district=districts[5], home=(41.29, 69.21))  # boshqa tuman, ~1 km
    await make_worker(db, 3, district=districts[5], home=FAR_AWAY)  # uzoq
    await make_worker(db, 4, verified=False)
    await make_worker(db, 5, spec=loader)  # boshqa mutaxassislik
    weekday = (datetime.now(TASHKENT) + timedelta(days=7)).weekday()
    await make_worker(db, 6, slots=[(weekday, time(8), time(12))])  # 8 soatlik ishga yetmaydi
    _, h = emp
    order_id = await create_order(client, h, db, start_in=timedelta(days=7))

    offers = await offers_of(db, order_id)
    assert {o.worker_id for o in offers} == {in_district, near_home}
    assert all(o.wave == 1 and o.status == "sent" for o in offers)
    assert sorted(c[1] for c in notifier.calls if c[0] == "offer_new") == sorted(o.id for o in offers)
    order = await db.get(Order, order_id)
    assert order.waves_sent == 1


async def test_urgent_requires_available_now(client, emp, db):
    await make_worker(db, 1)
    ready = await make_worker(db, 2, available=True)
    _, h = emp
    order_id = await create_order(client, h, db, start_in=timedelta(hours=1))
    offers = await offers_of(db, order_id)
    assert {o.worker_id for o in offers} == {ready}
    ttl = offers[0].expires_at.replace(tzinfo=UTC) - offers[0].sent_at.replace(tzinfo=UTC)
    assert ttl == timedelta(minutes=5)  # shoshilinch — 5 daqiqa


# ---------------- qabul / rad ----------------
async def test_accept_fills_slot_and_withdraws_rest(client, emp, db, redis, sms, notifier):
    w1, w2 = await make_worker(db, 1), await make_worker(db, 2)
    _, h = emp
    order_id = await create_order(client, h, db)
    offers = {o.worker_id: o for o in await offers_of(db, order_id)}
    h1 = await headers_for(client, db, w1, redis, sms)
    h2 = await headers_for(client, db, w2, redis, sms)

    r = await client.post(f"{API}/offers/{offers[w1].id}/accept", headers=h1)
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["address_text"].startswith("Chilonzor") and a["landmark"] == "Maktab yonida"
    assert a["employer_phone"] == "+998971234567"  # tayinlovdan keyin ochiladi
    assert ("worker_assigned", offers[w1].id) in notifier.calls

    # yagona o'rin to'ldi — ikkinchi taklif olib qo'yilgan
    r = await client.post(f"{API}/offers/{offers[w2].id}/accept", headers=h2)
    assert r.status_code == 409 and r.json()["code"] == "OFFER_WITHDRAWN"

    order = (await client.get(f"{API}/orders/{order_id}", headers=h)).json()
    assert order["status"] == "assigned"
    slot = order["assignments"][0]
    assert slot["worker_id"] == w1 and slot["worker_name"] == "Ishchi1 K." and slot["worker_phone"]
    mine = (await client.get(f"{API}/worker/assignments", headers=h1)).json()
    assert [m["order_id"] for m in mine] == [order_id]


async def test_offer_card_hides_address(client, emp, db, redis, sms):
    w1 = await make_worker(db, 1)
    _, h = emp
    await create_order(client, h, db)
    h1 = await headers_for(client, db, w1, redis, sms)
    offers = (await client.get(f"{API}/worker/offers", headers=h1)).json()
    assert len(offers) == 1 and offers[0]["worker_net"] == 150_000
    text = str(offers[0])
    assert "Chilonzor 9-kvartal" not in text and "+99897" not in text


async def test_decline_and_expired(client, emp, db, redis, sms):
    w1 = await make_worker(db, 1)
    _, h = emp
    order_id = await create_order(client, h, db)
    offer = (await offers_of(db, order_id))[0]
    h1 = await headers_for(client, db, w1, redis, sms)
    assert (await client.post(f"{API}/offers/{offer.id}/decline", headers=h1)).status_code == 204
    assert (await client.post(f"{API}/offers/{offer.id}/accept", headers=h1)).json()["code"] == "OFFER_DECLINED"

    w2 = await make_worker(db, 2)
    order2 = await create_order(client, h, db, key="k-000002", at="18:00")
    o2 = next(o for o in await offers_of(db, order2) if o.worker_id == w2)
    o2.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    h2 = await headers_for(client, db, w2, redis, sms)
    assert (await client.post(f"{API}/offers/{o2.id}/accept", headers=h2)).json()["code"] == "OFFER_EXPIRED"


async def test_foreign_offer_not_found(client, emp, db, redis, sms):
    w1, w2 = await make_worker(db, 1), await make_worker(db, 2)
    _, h = emp
    order_id = await create_order(client, h, db)
    offer = next(o for o in await offers_of(db, order_id) if o.worker_id == w1)
    h2 = await headers_for(client, db, w2, redis, sms)
    assert (await client.post(f"{API}/offers/{offer.id}/accept", headers=h2)).status_code == 404


async def test_time_conflict_excludes_from_next_wave(client, emp, db, redis, sms):
    w1 = await make_worker(db, 1)
    _, h = emp
    first = await create_order(client, h, db)
    h1 = await headers_for(client, db, w1, redis, sms)
    offer = (await offers_of(db, first))[0]
    assert (await client.post(f"{API}/offers/{offer.id}/accept", headers=h1)).status_code == 200
    # shu kuni 10:00 dagi ikkinchi buyurtma kesishadi — taklif bormaydi
    second = await create_order(client, h, db, key="k-000002", at="10:00")
    assert await offers_of(db, second) == []


# ---------------- scheduler ----------------
async def test_tick_expires_offers_and_sends_next_waves(client, emp, db, redis, notifier):
    ids = [await make_worker(db, i) for i in range(1, 9)]  # 8 ishchi, to'lqin — 5 ta
    _, h = emp
    order_id = await create_order(client, h, db)
    assert len(await offers_of(db, order_id)) == 5

    later = datetime.now(UTC) + timedelta(minutes=11)
    stats = await tick(db, redis, notifier, later)
    assert (stats["expired_offers"], stats["waves"], stats["offers"]) == (5, 1, 3)
    assert {o.worker_id for o in await offers_of(db, order_id)} == set(ids)  # 2-to'lqin — qolgan 3 kishi

    # 3-to'lqinga nomzod qolmadi → admin va employerga signal
    stats = await tick(db, redis, notifier, later + timedelta(minutes=11))
    assert stats["alerts"] == 1 and ("matching_exhausted", order_id) in notifier.calls


async def test_three_missed_offers_turn_off_available(client, emp, db, redis, notifier):
    w = await make_worker(db, 1, available=True)
    _, h = emp
    for i in range(3):
        await create_order(client, h, db, key=f"k-00000{i}", start_in=timedelta(days=2 + i))
    await tick(db, redis, notifier, datetime.now(UTC) + timedelta(minutes=11))
    profile = await db.get(WorkerProfile, w)
    await db.refresh(profile)
    assert profile.available_now_until is None
    assert ("worker_set_busy", w) in notifier.calls


async def test_past_unfilled_order_expires(client, emp, db, redis, notifier):
    _, h = emp
    order_id = await create_order(client, h, db)
    stats = await tick(db, redis, notifier, datetime.now(UTC) + timedelta(days=2))
    assert stats["expired_orders"] == 1
    order = await db.get(Order, order_id)
    await db.refresh(order)
    assert order.status == "expired"


# ---------------- ochiq lenta ----------------
async def test_open_feed_take(client, emp, db, redis, sms):
    for i in range(1, 6):
        await make_worker(db, i)
    _, h = emp
    order_id = await create_order(client, h, db, workers=2)
    # 6-ishchi to'lqindan keyin qo'shildi — taklif olmagan, lekin lentada ko'radi
    late = await make_worker(db, 6)
    hl = await headers_for(client, db, late, redis, sms)
    feed = (await client.get(f"{API}/jobs/open", headers=hl)).json()
    assert [j["order_id"] for j in feed] == [order_id] and feed[0]["open_slots"] == 2
    r = await client.post(f"{API}/jobs/{order_id}/take", headers=hl)
    assert r.status_code == 200 and r.json()["status"] == "assigned"
    assert (await client.get(f"{API}/jobs/open", headers=hl)).json() == []
    order = (await client.get(f"{API}/orders/{order_id}", headers=h)).json()
    assert order["status"] == "partially_assigned"


async def test_unverified_worker_cannot_use_feed(client, worker):
    _, h = await worker()
    r = await client.get(f"{API}/jobs/open", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "WORKER_NOT_VERIFIED"


async def test_available_now_toggle(client, db, redis, sms):
    w = await make_worker(db, 1)
    hw = await headers_for(client, db, w, redis, sms)
    r = (await client.post(f"{API}/worker/status", json={"available_now": True}, headers=hw)).json()
    assert r["available_now"] is True and r["until"]
    r = (await client.post(f"{API}/worker/status", json={"available_now": False}, headers=hw)).json()
    assert r == {"available_now": False, "until": None}


# ---------------- bot tugmalari ----------------
async def test_bot_accept_button(client, emp, db, maker, redis, settings, notifier):
    w = await make_worker(db, 1)
    _, h = emp
    order_id = await create_order(client, h, db)
    offer = (await offers_of(db, order_id))[0]

    session = FakeSession()
    bot = Bot(BOT_TOKEN, session=session)
    dp = create_dispatcher(maker, settings)
    dp.workflow_data.update(redis=redis, notifier=notifier)
    tg = TgUser(id=70001, is_bot=False, first_name="Ishchi1", language_code="uz")
    msg = Message(
        message_id=5, date=datetime.now(UTC), chat=Chat(id=70001, type="private"), from_user=tg, text="Yangi taklif"
    )
    update = Update(
        update_id=1,
        callback_query=CallbackQuery(id="cb1", from_user=tg, chat_instance="x", message=msg, data=f"of:a:{offer.id}"),
    )
    await dp.feed_update(bot, update)
    methods = [type(c).__name__ for c in session.calls]
    assert "AnswerCallbackQuery" in methods and "EditMessageText" in methods
    edit = next(c for c in session.calls if type(c).__name__ == "EditMessageText")
    assert "Qabul qildingiz" in edit.text
    db.expire_all()
    slot = await db.scalar(select(Assignment).where(Assignment.order_id == order_id))
    assert slot.worker_id == w and slot.status == "assigned"
