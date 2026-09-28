"""Botni API'siz, alohida polling rejimida ishga tushirish (dev uchun):
python -m workly.interfaces.bot
"""

import asyncio
import logging

from workly.infrastructure.config import get_settings
from workly.infrastructure.db.session import make_engine, make_sessionmaker

from .factory import create_bot, create_dispatcher, set_default_commands


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    from redis.asyncio import Redis

    from workly.interfaces.api.main import build_sms

    from .notifier import BotNotifier

    bot = create_bot(settings)
    maker = make_sessionmaker(engine)
    dp = create_dispatcher(maker, settings)
    redis = Redis.from_url(settings.redis_url)
    dp.workflow_data.update(redis=redis, notifier=BotNotifier(bot, maker, build_sms(settings), settings))
    await set_default_commands(bot)
    await bot.delete_webhook()
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
