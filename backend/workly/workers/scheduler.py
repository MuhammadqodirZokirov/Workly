"""Faza 1-lite rejalashtiruvchisi: API jarayoni ichida har 30 soniyada ishlaydi (TZ 6, 22-bo'limlar).
Bir nechta jarayon bo'lsa ham Redis qulfi tufayli bir vaqtda faqat bittasi bajaradi.
Muddatlar bazada saqlanadi — server qayta ishga tushsa ham yo'qolmaydi."""

import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import LockError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from workly.application.matching import MatchingService
from workly.application.notifications import Notifier
from workly.application.workday import WorkdayService
from workly.infrastructure.db.models import Order
from workly.infrastructure.storage import FileStorage

log = logging.getLogger(__name__)
TICK_SECONDS = 30


async def deliver_workday_outbox(
    svc: WorkdayService, maker, redis: Redis, notifier: Notifier, storage: FileStorage | None
) -> None:
    """WorkdayService commit'dan keyingi ishlari: bildirishnomalar, almashtirish to'lqini, fayllarni o'chirish."""
    for method, args in svc.outbox:
        try:
            if method == "replacement_wave":
                await start_matching(maker, redis, notifier, *args)
            else:
                await getattr(notifier, method)(*args)
        except Exception:
            log.exception("outbox %s%s bajarilmadi", method, args)
    svc.outbox = []
    if storage:
        for key in svc.files_to_delete:
            try:
                await storage.delete(key)
            except Exception:
                log.exception("fayl o'chirilmadi: %s", key)
    svc.files_to_delete = []


async def tick_once(
    maker: async_sessionmaker[AsyncSession], redis: Redis, notifier: Notifier, storage: FileStorage | None = None
) -> dict | None:
    lock = redis.lock("lock:scheduler", timeout=TICK_SECONDS * 2, blocking_timeout=0)
    if not await lock.acquire():
        return None
    try:
        # 1) Ish kuni: eslatmalar, kechikish, kelmaslik (almashtirish sloti ochiladi), avtotasdiq, avtobaho
        async with maker() as db:
            workday = WorkdayService(db, storage)
            wstats = await workday.tick()
            await db.commit()
        # 2) Matching: muddati o'tgan takliflar, keyingi to'lqinlar (almashtirish ham shu yerda)
        async with maker() as db:
            matching = MatchingService(db, redis, notifier)
            mstats = await matching.tick()
            await db.commit()
        workday.outbox = [x for x in workday.outbox if x[0] != "replacement_wave"]  # 2-qadam yubordi
        await deliver_workday_outbox(workday, maker, redis, notifier, storage)
        await matching.flush_outbox()
        stats = {**wstats, **mstats}
        if any(stats.values()):
            log.info("scheduler: %s", stats)
        return stats
    finally:
        try:
            await lock.release()
        except LockError:
            pass


async def run_forever(
    maker, redis: Redis, notifier: Notifier, stop: asyncio.Event, storage: FileStorage | None = None
) -> None:
    while not stop.is_set():
        try:
            await tick_once(maker, redis, notifier, storage)
        except Exception:
            log.exception("scheduler tick xatosi")
        try:
            await asyncio.wait_for(stop.wait(), timeout=TICK_SECONDS)
        except TimeoutError:
            pass


async def start_matching(maker, redis: Redis, notifier: Notifier, order_id: int) -> None:
    """Yangi buyurtma yoki almashtirish — to'lqinni darhol yuborish (commit'dan keyin chaqiriladi)."""
    try:
        async with maker() as db:
            order = await db.get(Order, order_id)
            if order is None:
                return
            await db.refresh(order, attribute_names=["assignments"])
            svc = MatchingService(db, redis, notifier)
            await svc.run_wave(order)
            await db.commit()
        await svc.flush_outbox()
    except Exception:
        log.exception("order=%s to'lqin yuborilmadi (scheduler qayta urinadi)", order_id)
