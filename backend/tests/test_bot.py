import datetime

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import Chat, Contact, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import select

from rabotago.application.users import UserService
from rabotago.domain.errors import Conflict
from rabotago.infrastructure.db.models import User
from rabotago.interfaces.bot.factory import create_dispatcher

from .conftest import BOT_TOKEN


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        self.calls.append(method)
        return True

    async def close(self):
        pass

    async def stream_content(self, *a, **k):
        yield b""


@pytest.fixture
def bot_env(maker, settings):
    session = FakeSession()
    bot = Bot(BOT_TOKEN, session=session)
    s = settings.model_copy(update={"webapp_url": "https://app.rabotago.uz"})
    return bot, create_dispatcher(maker, s), session


def _msg(n, *, text=None, contact=None, uid=42):
    return Update(
        update_id=n,
        message=Message(
            message_id=n,
            date=datetime.datetime.now(datetime.UTC),
            chat=Chat(id=uid, type="private"),
            from_user=TgUser(id=uid, is_bot=False, first_name="Ali <b>", language_code="uz"),
            text=text,
            contact=contact,
        ),
    )


async def test_start_asks_phone_then_contact_links(bot_env, db):
    bot, dp, session = bot_env
    await dp.feed_update(bot, _msg(1, text="/start"))
    texts = [c.text for c in session.calls]
    assert "Ali &lt;b&gt;" in texts[0]  # ism HTML ekranlangan
    assert session.calls[1].reply_markup.keyboard[0][0].request_contact is True

    session.calls.clear()
    contact = Contact(phone_number="998901234567", first_name="Ali", user_id=42)
    await dp.feed_update(bot, _msg(2, contact=contact))
    assert "tasdiqlandi" in session.calls[0].text
    assert session.calls[1].reply_markup.inline_keyboard[0][0].web_app.url == "https://app.rabotago.uz"

    user = await db.scalar(select(User).where(User.telegram_id == 42))
    assert user.phone == "+998901234567" and user.phone_verified_at is not None


async def test_foreign_contact_rejected(bot_env, db):
    bot, dp, session = bot_env
    contact = Contact(phone_number="998901234567", first_name="Boshqa", user_id=999)
    await dp.feed_update(bot, _msg(1, contact=contact))
    assert "o'zingizning" in session.calls[0].text
    assert await db.scalar(select(User)) is None


async def test_link_merges_into_sms_account(db, client, login):
    body, _ = await login("+998907777777")
    # Telegram orqali (raqamsiz) ochilgan bo'sh akkaunt
    tg_only = User(telegram_id=555)
    db.add(tg_only)
    await db.commit()

    user = await UserService(db).link_telegram_phone(555, "+998907777777")
    await db.commit()
    assert user.id == body["user"]["id"] and user.telegram_id == 555
    await db.refresh(tg_only)
    assert tg_only.status == "deleted" and tg_only.telegram_id is None


async def test_link_conflict_when_phone_has_other_telegram(db):
    db.add(User(telegram_id=1, phone="+998901000000"))
    await db.commit()
    with pytest.raises(Conflict):
        await UserService(db).link_telegram_phone(2, "+998901000000")
