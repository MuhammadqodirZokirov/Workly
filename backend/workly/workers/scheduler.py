"""Faza 1-lite rejalashtiruvchisi: API jarayoni ichida har 30 soniyada ishlaydi (TZ 6, 22-bo'limlar).
Bir nechta jarayon bo'lsa ham Redis qulfi tufayli bir vaqtda faqat bittasi bajaradi."""

import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workly.application.matching import MatchingService
from workly.application.notifications import Notifier
from workly.infrastructure.db.models import Order

log = logging.getLogger(__name__)
TICK_SECONDS = 30


async def tick_once(maker: async_sessionmaker[AsyncSession], redis: Redis, notifier: Notifier) -> dict | None:
    lock = redis.lock("lock:scheduler", timeout=TICK_SECONDS * 2, blocking_timeout=0)
    if not await lock.acquire():
        return None
    try:
        async with maker() as db:
            svc = MatchingService(db, redis, notifier)
            stats = await svc.tick()
            await db.commit()
        await svc.flush_outbox()
        if any(stats.values()):
            log.info("scheduler: %s", stats)
        return stats
    finally:
        try:
            await lock.release()
        except LockError:
            pass


async def run_forever(maker, redis: Redis, notifier: Notifier, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await tick_once(maker, redis, notifier)
        except Exception:
            log.exception("scheduler tick xatosi")
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_SECONDS)
        except TimeoutError:
            pass


async def start_matching(maker, redis: Redis, notifier: Notifier, order_id: int) -> None:
    """Buyurtma yaratilgach birinchi to'lqinni darhol yuborish (commit'dan keyin chaqiriladi)."""
    try:
        async with maker() as db:
            order = await db.get(Order, order_id)
            if order is None:
                return
            svc = MatchingService(db, redis, notifier)
            await svc.run_wave(order)
            await db.commit()
        await svc.flush_outbox()
    except Exception:
        log.exception("order=%s birinchi to'lqin yuborilmadi (scheduler qayta uriniadi)", order_id)
