from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from workly.infrastructure.db.models import User
from workly.interfaces.bot.notifier import BotNotifier

from .conftest import BOT_TOKEN
from .test_bot import FakeSession


class ForbiddenSession(FakeSession):
    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        raise TelegramForbiddenError(method=method, message="bot was blocked by the user")


async def _user(db, **kw) -> int:
    user = User(**kw)
    db.add(user)
    await db.commit()
    return user.id


async def test_bot_message_in_user_language(db, maker, sms):
    uid = await _user(db, telegram_id=10, phone="+998901112233", lang="ru")
    session = FakeSession()
    await BotNotifier(Bot(BOT_TOKEN, session=session), maker, sms).verification_result(uid, False, "blurry")
    assert session.calls[0].chat_id == 10
    assert "нечёткое фото" in session.calls[0].text
    assert sms.sent == []


async def test_sms_fallback_when_bot_blocked(db, maker, sms):
    uid = await _user(db, telegram_id=11, phone="+998901112244")
    bot = Bot(BOT_TOKEN, session=ForbiddenSession())
    await BotNotifier(bot, maker, sms).verification_result(uid, True, None)
    assert sms.sent == [("+998901112244", "Workly: ✅ Profilingiz tasdiqlandi! Endi ish takliflarini olasiz.")]


async def test_sms_when_no_telegram(db, maker, sms):
    uid = await _user(db, phone="+998901112255", lang="uz_cyrl")
    await BotNotifier(None, maker, sms).verification_result(uid, True, None)
    assert "тасдиқланди" in sms.sent[0][1]
