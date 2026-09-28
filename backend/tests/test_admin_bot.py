import datetime

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from workly.application.pricing import PriceService
from workly.infrastructure.db.models import (
    AuditLog,
    Category,
    District,
    Review,
    Specialization,
    User,
    UserRole,
)
from workly.interfaces.admin_bot.factory import create_admin_dispatcher
from workly.interfaces.bot.notifier import BotNotifier

from .conftest import BOT_TOKEN
from .test_bot import FakeSession

ADMIN_TG, MOD_TG, STRANGER_TG = 500, 501, 502
NOW = datetime.datetime.now(datetime.UTC)


@pytest.fixture
async def staff(db):
    for tg, role, phone in ((ADMIN_TG, "admin", "+998900000500"), (MOD_TG, "moderator", "+998900000501")):
        user = User(telegram_id=tg, phone=phone, full_name=f"{role} xodim")
        user.roles.append(UserRole(role=role))
        db.add(user)
    await db.commit()


@pytest.fixture
def env(maker, settings, staff):
    session = FakeSession()
    return Bot(BOT_TOKEN, session=session), create_admin_dispatcher(maker, settings), session


class Feed:
    """Bot bilan suhbat: xabar va tugma bosish."""

    def __init__(self, env, tg_id=ADMIN_TG):
        self.bot, self.dp, self.session = env
        self.tg_id, self.n = tg_id, 0

    def _user(self):
        return TgUser(id=self.tg_id, is_bot=False, first_name="Xodim")

    def _message(self, text=None):
        self.n += 1
        return Message(
            message_id=self.n,
            date=NOW,
            chat=Chat(id=self.tg_id, type="private"),
            from_user=self._user(),
            text=text,
        )

    async def say(self, text):
        self.session.calls.clear()
        await self.dp.feed_update(self.bot, Update(update_id=self._next(), message=self._message(text)))
        return self.session.calls

    async def press(self, data):
        self.session.calls.clear()
        cb = CallbackQuery(
            id=str(self._next()), from_user=self._user(), chat_instance="x", data=data, message=self._message("menu")
        )
        await self.dp.feed_update(self.bot, Update(update_id=self._next(), callback_query=cb))
        return self.session.calls

    def _next(self):
        self.n += 1
        return self.n


def texts(calls):
    return [getattr(c, "text", None) for c in calls if getattr(c, "text", None)]


def buttons(calls):
    out = []
    for c in calls:
        markup = getattr(c, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", None) or []:
            out += [(b.text, b.callback_data) for b in row]
    return out


async def test_access_control(env):
    calls = await Feed(env, STRANGER_TG).say("/start")
    assert "Ruxsat yo'q" in texts(calls)[0] and str(STRANGER_TG) in texts(calls)[0]

    admin_menu = [t for t, _ in buttons(await Feed(env).say("/start"))]
    assert {"🗂 Kategoriyalar", "💰 Narxlar", "📍 Hududlar", "📊 Bugungi statistika"} <= set(admin_menu)

    mod = Feed(env, MOD_TG)
    assert [t for t, _ in buttons(await mod.say("/start"))] == ["📊 Bugungi statistika"]
    calls = await mod.press("m:cats")  # moderatorga sozlamalar yopiq
    assert any(getattr(c, "text", "") == "Bu bo'lim faqat admin uchun" for c in calls)
    assert "Verifikatsiya kutmoqda" in texts(await mod.say("/stats"))[0]


async def test_create_category_and_specialization(env, db):
    f = Feed(env)
    await f.press("c:new:0")
    await f.say("Plitka ishlari")
    preview = texts(await f.say("Плиточные работы"))[0]
    assert "Плитка ишлари" in preview and "Saqlaysizmi?" in preview  # kirill avtomatik
    assert "✅ Saqlandi" in texts(await f.press("ok:1"))[0]

    cat = await db.scalar(select(Category).where(Category.code == "plitka_ishlari"))
    assert (cat.name_uz_cyrl, cat.name_ru, cat.is_active) == ("Плитка ишлари", "Плиточные работы", True)

    await f.press(f"c:new_spec:{cat.id}")
    await f.say("x")  # juda qisqa — qayta so'raladi
    assert "Lotin nomini qayta yozing" in texts(await f.say("Плитка"))[0]
    await f.say("Kafel yotqizish")
    await f.say("Укладка кафеля")
    await f.press("ok:0")  # bekor
    assert await db.scalar(select(Specialization).where(Specialization.category_id == cat.id)) is None
    await f.press(f"c:new_spec:{cat.id}")
    await f.say("Kafel yotqizish")
    await f.say("Укладка кафеля")
    await f.press("ok:1")
    spec = await db.scalar(select(Specialization).where(Specialization.category_id == cat.id))
    assert spec.code == "kafel_yotqizish"

    # Takror nom — xato
    await f.press("c:new:0")
    await f.say("Plitka ishlari")
    await f.say("Плиточные")
    assert "Bunday kategoriya bor" in texts(await f.press("ok:1"))[0]
    actions = set(await db.scalars(select(AuditLog.action)))
    assert {"catalog.category.create", "catalog.specialization.create"} <= actions


async def test_toggle_specialization_and_district(env, db):
    f = Feed(env)
    spec = await db.scalar(select(Specialization).where(Specialization.code == "loader"))
    calls = await f.press(f"c:spec:{spec.id}")
    assert any(getattr(c, "text", "") == "O'chirildi" for c in calls)
    assert await db.scalar(select(Specialization.is_active).where(Specialization.id == spec.id)) is False
    await f.press(f"c:spec:{spec.id}")
    assert await db.scalar(select(Specialization.is_active).where(Specialization.id == spec.id)) is True

    district = await db.scalar(select(District).order_by(District.id))
    await f.press(f"d:{district.id}")
    assert await db.scalar(select(District.is_active).where(District.id == district.id)) is False


async def test_price_edit(env, db):
    f = Feed(env)
    spec = await db.scalar(select(Specialization).where(Specialization.code == "general"))
    await f.press(f"p:item:{spec.category_id}:{spec.id}")
    assert "1 000 dan" in texts(await f.say("50"))[0]
    preview = texts(await f.say("160 000"))[0]
    assert "160 000 so'm / kun" in preview and "120 000" in preview and "320 000" in preview
    assert "✅ Narx saqlandi" in texts(await f.press("ok:1"))[0]
    current = {(r.category_id, r.specialization_id): r for r in await PriceService(db).current()}
    row = current[(spec.category_id, spec.id)]
    assert (row.base, row.min_price, row.max_price, row.unit) == (160_000, 120_000, 320_000, "day")


async def test_hide_auto_review(env, db, emp_order_reviews):
    review_id = emp_order_reviews
    f = Feed(env)
    listing = texts(await f.press("m:auto"))[0]
    assert f"#{review_id}" in listing
    await f.press(f"r:{review_id}")
    assert await db.scalar(select(Review.hidden_by_admin).where(Review.id == review_id)) is True


@pytest.fixture
async def emp_order_reviews(db):
    """Tasdiqlangan tayinlov va unga 48 soatdan keyin qo'yilgan avtomatik baho."""
    from workly.infrastructure.db.models import Assignment, Order

    spec = await db.scalar(select(Specialization).where(Specialization.code == "general"))
    district = await db.scalar(select(District).order_by(District.id))
    a, b = User(phone="+998900000601"), User(phone="+998900000602")
    db.add_all([a, b])
    await db.flush()
    order = Order(
        employer_id=a.id,
        category_id=spec.category_id,
        specialization_id=spec.id,
        workers_count=1,
        starts_at=NOW,
        lat=41.3,
        lon=69.2,
        district_id=district.id,
        address_text="x",
        price={"worker_price": 150_000},
        status="completed",
    )
    order.assignments = [Assignment(slot_no=1, worker_id=b.id, status="confirmed")]
    db.add(order)
    await db.flush()
    review = Review(
        assignment_id=order.assignments[0].id,
        author_id=a.id,
        target_id=b.id,
        target_role="worker",
        rating=4.5,
        tags=[],
        is_auto=True,
        visible_at=NOW,
    )
    db.add(review)
    await db.commit()
    return review.id


async def test_signals_go_to_staff_via_admin_bot(db, maker, sms, settings, staff):
    main, admin = FakeSession(), FakeSession()
    s = settings.model_copy(update={"webapp_url": "https://app.workly.uz", "admins": [999]})
    notifier = BotNotifier(Bot(BOT_TOKEN, session=main), maker, sms, s, admin_bot=Bot(BOT_TOKEN, session=admin))
    await notifier.admin_signal("verification", 42)
    assert main.calls == []
    assert {c.chat_id for c in admin.calls} == {ADMIN_TG, MOD_TG, 999}
    assert "https://app.workly.uz/admin/verifications/42" in admin.calls[0].text
