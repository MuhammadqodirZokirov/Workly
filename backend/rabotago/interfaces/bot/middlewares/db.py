from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """Har update uchun DB sessiya: handlerga `db` nomi bilan beriladi; xatosiz tugasa commit."""

    def __init__(self, maker: async_sessionmaker[AsyncSession]):
        self.maker = maker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.maker() as session:
            data["db"] = session
            result = await handler(event, data)
            await session.commit()
            return result
