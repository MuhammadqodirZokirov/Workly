"""Botni API'siz, alohida polling rejimida ishga tushirish (dev uchun):
python -m rabotago.interfaces.bot
"""

import asyncio
import logging

from rabotago.infrastructure.config import get_settings
from rabotago.infrastructure.db.session import make_engine, make_sessionmaker

from .factory import create_bot, create_dispatcher, set_default_commands


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    bot = create_bot(settings)
    dp = create_dispatcher(make_sessionmaker(engine), settings)
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
