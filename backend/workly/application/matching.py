"""Matching: nomzodlar, to'lqinlar, qabul/rad, ochiq lenta va rejalashtiruvchi qadami (TZ 7-bo'lim)."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Forbidden, InvalidState, NotFound
from workly.domain.matching import (
    AVAILABLE_NOW_TTL,
    DISTRICT_ONLY_KM,
    MAX_DISTANCE_KM,
    MAX_MISSED_STREAK,
    MAX_WAVES,
    MIN_RELIABILITY,
    WorkerSignals,
    compose_wave,
    fits_schedule,
    haversine_km,
    job_hours,
    job_window,
    offer_ttl,
    overlaps,
    score,
    wave_size,
)
from workly.domain.orders import (
    BUSY_ASSIGNMENT_STATUSES,
    MATCHING_STATUSES,
    AssignmentStatus,
    OfferStatus,
    OrderStatus,
    derive_status,
    ensure_order_transition,
)
from workly.domain.users import Role, UserStatus
from workly.domain.worker import VerificationStatus
from workly.infrastructure.db.models import (
    Assignment,
    Offer,
    Order,
    User,
    WorkerProfile,
    WorkerSpecialization,
)

from .audit import record_transition
from .notifications import Notifier

log = logging.getLogger(__name__)
TASHKENT = ZoneInfo("Asia/Tashkent")
LOCK_TIMEOUT = 10


def utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


@dataclass
class Candidate:
    profile: WorkerProfile
    signals: WorkerSignals
    score: float


class MatchingService:
    def __init__(self, db: AsyncSession, redis: Redis, notifier: Notifier, now: datetime | None = None):
        self.db, self.redis, self.notifier = db, redis, notifier
        self.now = now or datetime.now(UTC)
        # Bildirishnomalar commit'dan KEYIN yuboriladi (notifier o'z sessiyasida o'qiydi)
        self.outbox: list[tuple[str, tuple]] = []

    async def flush_outbox(self) -> None:
        items, self.outbox = self.outbox, []
        for method, args in items:
            try:
                await getattr(self.notifier, method)(*args)
            except Exception:
                log.exception("Bildirishnoma yuborilmadi: %s%s", method, args)

    # ================= nomzodlar =================
    async def _busy_windows(self, worker_ids: list[int]) -> dict[int, list[tuple[datetime, datetime]]]:
        if not worker_ids:
            return {}
        rows = await self.db.execute(
            select(Assignment.worker_id, Order.starts_at, Order.duration, Order.days)
            .join(Order, Order.id == Assignment.order_id)
            .where(Assignment.worker_id.in_(worker_ids), Assignment.status.in_(BUSY_ASSIGNMENT_STATUSES))
        )
        out: dict[int, list] = {}
        for wid, starts_at, duration, days in rows:
            out.setdefault(wid, []).append(job_window(utc(starts_at), duration, days))
        return out

    async def _history(self, worker_ids: list[int]) -> dict[int, dict]:
        """C (bajarish ulushi), T (javob tezligi), A (faollik) uchun 90 kunlik tarix."""
        since = self.now - timedelta(days=90)
        hist = {w: {"accepted": 0, "done": 0, "resp": [], "last": None} for w in worker_ids}
        if not worker_ids:
            return hist
        rows = await self.db.execute(
            select(Assignment.worker_id, Assignment.status, Order.starts_at)
            .join(Order, Order.id == Assignment.order_id)
            .where(Assignment.worker_id.in_(worker_ids), Order.starts_at >= since)
        )
        for wid, status, starts_at in rows:
            h = hist[wid]
            h["accepted"] += 1
            if status in (AssignmentStatus.FINISHED, AssignmentStatus.CONFIRMED):
                h["done"] += 1
                h["last"] = max(filter(None, [h["last"], utc(starts_at)]))
        rows = await self.db.execute(
            select(Offer.worker_id, Offer.sent_at, Offer.responded_at).where(
                Offer.worker_id.in_(worker_ids), Offer.responded_at.is_not(None), Offer.wave > 0, Offer.sent_at >= since
            )
        )
        for wid, sent, responded in rows:
            hist[wid]["resp"].append((utc(responded) - utc(sent)).total_seconds() / 60)
        return hist

    async def candidates(
        self, order: Order, *, only_worker: int | None = None, for_feed: bool = False
    ) -> list[Candidate]:
        q = (
            select(WorkerProfile)
            .join(User, User.id == WorkerProfile.user_id)
            .join(WorkerSpecialization, WorkerSpecialization.user_id == WorkerProfile.user_id)
            .where(
                WorkerProfile.verification_status == VerificationStatus.VERIFIED,
                User.status == UserStatus.ACTIVE,
                WorkerSpecialization.specialization_id == order.specialization_id,
                WorkerProfile.reliability >= MIN_RELIABILITY,
                WorkerProfile.user_id != order.employer_id,
            )
        )
        if only_worker is not None:
            q = q.where(WorkerProfile.user_id == only_worker)
        profiles = list((await self.db.scalars(q)).unique())
        ids = [p.user_id for p in profiles]
        busy = await self._busy_windows(ids)
        hist = await self._history(ids)
        starts_at = utc(order.starts_at)
        window = job_window(starts_at, order.duration, order.days)
        local = starts_at.astimezone(TASHKENT)
        urgent = starts_at - self.now <= timedelta(hours=2)

        out = []
        for p in profiles:
            # Hudud: tanlangan tumanlarda yoki uy nuqtasidan 10 km ichida
            in_district = order.district_id in {d.district_id for d in p.districts}
            distance = haversine_km(p.home_lat, p.home_lon, order.lat, order.lon) if p.home_lat is not None else None
            if not in_district and (distance is None or distance > MAX_DISTANCE_KM):
                continue
            if distance is None:
                distance = DISTRICT_ONLY_KM
            # Vaqti kesishgan boshqa tayinlov yo'q
            if any(overlaps(window, w) for w in busy.get(p.user_id, [])):
                continue
            if not for_feed:
                if urgent:
                    if not (p.available_now_until and utc(p.available_now_until) > self.now):
                        continue
                elif not fits_schedule(
                    [(a.weekday, a.start, a.end) for a in p.availability],
                    local.weekday(),
                    local.time(),
                    job_hours(order.duration),
                ):
                    continue
            # TODO(3-blok): reyting < 3.5 (≥ 5 baho) — baholar jadvali bilan; employer bloklagan ishchilar
            h = hist[p.user_id]
            skill = next((s for s in p.skills if s.category_id == order.category_id), None)
            signals = WorkerSignals(
                worker_id=p.user_id,
                rating=None,
                reviews_count=0,
                completion_rate=h["done"] / h["accepted"] if h["accepted"] else None,
                avg_response_min=sum(h["resp"]) / len(h["resp"]) if h["resp"] else None,
                distance_km=round(distance, 2),
                experience=skill.experience if skill else "none",
                days_since_last_job=(self.now - h["last"]).days if h["last"] else None,
            )
            out.append(Candidate(p, signals, score(signals)))
        out.sort(key=lambda c: (-c.score, c.signals.distance_km, c.profile.user_id))
        return out

    # ================= to'lqin =================
    async def run_wave(self, order: Order) -> list[Offer]:
        if order.status not in MATCHING_STATUSES or utc(order.starts_at) <= self.now:
            return []
        free = sum(1 for a in order.assignments if a.status == AssignmentStatus.OPEN)
        if free == 0 or order.waves_sent >= MAX_WAVES:
            return []
        offered = set((await self.db.scalars(select(Offer.worker_id).where(Offer.order_id == order.id))).all())
        assigned = {a.worker_id for a in order.assignments if a.worker_id}
        ranked = [c for c in await self.candidates(order) if c.profile.user_id not in offered | assigned]
        by_id = {c.profile.user_id: c for c in ranked}
        wave_no = order.waves_sent + 1
        chosen = compose_wave([c.signals for c in ranked], wave_size(free))
        expires = self.now + offer_ttl(utc(order.starts_at), self.now)
        offers = [
            Offer(
                order_id=order.id,
                worker_id=s.worker_id,
                wave=wave_no,
                score=by_id[s.worker_id].score,
                distance_km=s.distance_km,
                status=OfferStatus.SENT,
                sent_at=self.now,
                expires_at=expires,
            )
            for s in chosen
        ]
        self.db.add_all(offers)
        order.waves_sent = wave_no if offers else MAX_WAVES  # nomzod yo'q — keyingi to'lqin ham bo'sh
        order.last_wave_at = self.now
        await self.db.flush()
        self.outbox.extend(("offer_new", (o.id,)) for o in offers)
        log.info("order=%s wave=%s offers=%s", order.id, wave_no, len(offers))
        return offers

    # ================= qabul / rad =================
    async def _worker_profile(self, user: User) -> WorkerProfile:
        if Role.WORKER not in user.role_names:
            raise Forbidden("Avval ishchi rolini qo'shing", code="NOT_A_WORKER")
        profile = await self.db.get(WorkerProfile, user.id)
        if profile is None or profile.verification_status != VerificationStatus.VERIFIED:
            raise Forbidden("Profil hali tasdiqlanmagan", code="WORKER_NOT_VERIFIED")
        return profile

    async def accept(self, user: User, offer_id: int) -> Offer:
        profile = await self._worker_profile(user)
        offer = await self.db.get(Offer, offer_id)
        if offer is None or offer.worker_id != user.id:
            raise NotFound("Taklif topilmadi", code="OFFER_NOT_FOUND")
        async with (
            self.redis.lock(f"lock:order:{offer.order_id}", timeout=LOCK_TIMEOUT, blocking_timeout=5),
            self.redis.lock(f"lock:worker:{user.id}", timeout=LOCK_TIMEOUT, blocking_timeout=5),
        ):
            await self.db.refresh(offer)
            if offer.status != OfferStatus.SENT:
                raise InvalidState("Taklif endi faol emas", code=f"OFFER_{offer.status.upper()}")
            if utc(offer.expires_at) <= self.now:
                offer.status = OfferStatus.EXPIRED
                await self.db.flush()
                raise InvalidState("Taklif muddati tugagan", code="OFFER_EXPIRED")
            await self._assign(offer, profile)
        return offer

    async def _assign(self, offer: Offer, profile: WorkerProfile) -> Assignment:
        order = await self.db.scalar(select(Order).where(Order.id == offer.order_id).with_for_update())
        await self.db.refresh(order, attribute_names=["assignments"])
        if order.status not in MATCHING_STATUSES or utc(order.starts_at) <= self.now:
            offer.status = OfferStatus.WITHDRAWN
            await self.db.flush()
            raise InvalidState("Buyurtma endi ochiq emas", code="ORDER_CLOSED")
        if any(a.worker_id == offer.worker_id for a in order.assignments if a.status != AssignmentStatus.CANCELLED):
            raise InvalidState("Siz bu buyurtmaga allaqachon tayinlangansiz", code="ALREADY_ASSIGNED")
        slot = next((a for a in order.assignments if a.status == AssignmentStatus.OPEN), None)
        if slot is None:
            offer.status = OfferStatus.WITHDRAWN
            await self.db.flush()
            raise InvalidState("Barcha o'rinlar band bo'ldi", code="SLOTS_FILLED")
        window = job_window(utc(order.starts_at), order.duration, order.days)
        busy = (await self._busy_windows([offer.worker_id])).get(offer.worker_id, [])
        if any(overlaps(window, w) for w in busy):
            raise InvalidState("Shu vaqtda boshqa ishingiz bor", code="TIME_CONFLICT")

        slot.worker_id = offer.worker_id
        slot.status = AssignmentStatus.ASSIGNED
        offer.status = OfferStatus.ACCEPTED
        offer.responded_at = self.now
        offer.assignment_id = slot.id
        profile.missed_offers_streak = 0
        record_transition(
            self.db, "assignment", slot.id, AssignmentStatus.OPEN, AssignmentStatus.ASSIGNED, offer.worker_id
        )
        await self._update_order_status(order, offer.worker_id)
        if order.status == OrderStatus.ASSIGNED:
            # Slot to'ldi — qolgan takliflar WITHDRAWN (TZ 6-bo'lim)
            others = await self.db.scalars(
                select(Offer).where(Offer.order_id == order.id, Offer.status == OfferStatus.SENT, Offer.id != offer.id)
            )
            for o in others:
                o.status = OfferStatus.WITHDRAWN
        await self.db.flush()
        return slot

    async def _update_order_status(self, order: Order, actor_id: int | None) -> None:
        open_ = sum(1 for a in order.assignments if a.status == AssignmentStatus.OPEN)
        filled = sum(1 for a in order.assignments if a.status in BUSY_ASSIGNMENT_STATUSES)
        new = derive_status(open_, filled)
        if new != order.status:
            ensure_order_transition(order.status, new)
            record_transition(self.db, "order", order.id, order.status, new, actor_id)
            order.status = new

    async def decline(self, user: User, offer_id: int) -> Offer:
        offer = await self.db.get(Offer, offer_id)
        if offer is None or offer.worker_id != user.id:
            raise NotFound("Taklif topilmadi", code="OFFER_NOT_FOUND")
        if offer.status != OfferStatus.SENT:
            raise InvalidState("Taklif endi faol emas", code=f"OFFER_{offer.status.upper()}")
        # Rad etish jazolanmaydi (TZ 7-bo'lim)
        offer.status = OfferStatus.DECLINED
        offer.responded_at = self.now
        profile = await self.db.get(WorkerProfile, user.id)
        if profile:
            profile.missed_offers_streak = 0
        await self.db.flush()
        return offer

    # ================= ochiq lenta =================
    async def open_feed(self, user: User, limit: int = 50) -> list[tuple[Order, Candidate]]:
        profile = await self._worker_profile(user)
        spec_ids = [s.specialization_id for s in profile.specializations]
        if not spec_ids:
            return []
        orders = await self.db.scalars(
            select(Order)
            .where(
                Order.status.in_(MATCHING_STATUSES),
                Order.waves_sent >= 1,
                Order.starts_at > self.now,
                Order.specialization_id.in_(spec_ids),
                Order.employer_id != user.id,
            )
            .order_by(Order.starts_at)
            .limit(200)
        )
        out = []
        for order in orders:
            if any(a.worker_id == user.id for a in order.assignments):
                continue
            if not any(a.status == AssignmentStatus.OPEN for a in order.assignments):
                continue
            match = await self.candidates(order, only_worker=user.id, for_feed=True)
            if match:
                out.append((order, match[0]))
            if len(out) >= limit:
                break
        return out

    async def take_from_feed(self, user: User, order_id: int) -> Offer:
        """Lentadan olish: birinchi qabul qilgan oladi."""
        profile = await self._worker_profile(user)
        order = await self.db.get(Order, order_id)
        if order is None or order.waves_sent < 1 or order.employer_id == user.id:
            raise NotFound("Ish topilmadi", code="JOB_NOT_FOUND")
        match = await self.candidates(order, only_worker=user.id, for_feed=True)
        if not match:
            raise Forbidden("Bu ish sizga mos emas", code="JOB_NOT_ELIGIBLE")
        async with (
            self.redis.lock(f"lock:order:{order_id}", timeout=LOCK_TIMEOUT, blocking_timeout=5),
            self.redis.lock(f"lock:worker:{user.id}", timeout=LOCK_TIMEOUT, blocking_timeout=5),
        ):
            offer = await self.db.scalar(
                select(Offer).where(
                    Offer.order_id == order_id, Offer.worker_id == user.id, Offer.status == OfferStatus.SENT
                )
            )
            if offer is None:
                offer = Offer(
                    order_id=order_id,
                    worker_id=user.id,
                    wave=0,
                    score=match[0].score,
                    distance_km=match[0].signals.distance_km,
                    status=OfferStatus.SENT,
                    sent_at=self.now,
                    expires_at=self.now + timedelta(minutes=1),
                )
                self.db.add(offer)
                await self.db.flush()
            await self._assign(offer, profile)
        return offer

    # ================= ishchi holati =================
    async def set_available(self, user: User, available: bool) -> WorkerProfile:
        profile = await self._worker_profile(user)
        profile.available_now_until = self.now + AVAILABLE_NOW_TTL if available else None
        profile.missed_offers_streak = 0
        await self.db.flush()
        return profile

    async def active_offers(self, user: User) -> list[Offer]:
        rows = await self.db.scalars(
            select(Offer)
            .where(Offer.worker_id == user.id, Offer.status == OfferStatus.SENT, Offer.expires_at > self.now)
            .order_by(Offer.expires_at)
        )
        return list(rows)

    async def my_assignments(self, user: User) -> list[Assignment]:
        rows = await self.db.scalars(
            select(Assignment)
            .join(Order)
            .where(Assignment.worker_id == user.id, Assignment.status.in_(BUSY_ASSIGNMENT_STATUSES))
            .order_by(Order.starts_at)
        )
        return list(rows)

    # ================= rejalashtiruvchi qadami =================
    async def tick(self) -> dict:
        """Har 30 soniyada: muddati o'tgan takliflar, keyingi to'lqinlar, o'tib ketgan buyurtmalar.
        Holat bazada saqlanadi — server qayta ishga tushsa ham muddatlar yo'qolmaydi (TZ 6-bo'lim)."""
        stats = {"expired_offers": 0, "waves": 0, "offers": 0, "alerts": 0, "expired_orders": 0}

        expired = list(
            await self.db.scalars(select(Offer).where(Offer.status == OfferStatus.SENT, Offer.expires_at <= self.now))
        )
        for offer in expired:
            offer.status = OfferStatus.EXPIRED
            if offer.wave == 0:
                continue
            profile = await self.db.get(WorkerProfile, offer.worker_id)
            if profile is None:
                continue
            profile.missed_offers_streak += 1
            if profile.missed_offers_streak >= MAX_MISSED_STREAK:
                # Ketma-ket 3 ta javobsiz taklif — "Band" (TZ 7-bo'lim)
                profile.missed_offers_streak = 0
                if profile.available_now_until is not None:
                    profile.available_now_until = None
                self.outbox.append(("worker_set_busy", (profile.user_id,)))
        stats["expired_offers"] = len(expired)
        await self.db.flush()

        orders = list(await self.db.scalars(select(Order).where(Order.status.in_(MATCHING_STATUSES))))
        for order in orders:
            if utc(order.starts_at) <= self.now:
                if order.status == OrderStatus.MATCHING:
                    ensure_order_transition(order.status, OrderStatus.EXPIRED)
                    record_transition(
                        self.db, "order", order.id, order.status, OrderStatus.EXPIRED, None, reason="ishchi topilmadi"
                    )
                    order.status = OrderStatus.EXPIRED
                    for a in order.assignments:
                        a.status = AssignmentStatus.CANCELLED
                    stats["expired_orders"] += 1
                continue
            if not any(a.status == AssignmentStatus.OPEN for a in order.assignments):
                continue
            active = await self.db.scalar(
                select(Offer.id).where(Offer.order_id == order.id, Offer.status == OfferStatus.SENT).limit(1)
            )
            if active is not None:
                continue
            if order.waves_sent < MAX_WAVES:
                offers = await self.run_wave(order)
                if offers:
                    stats["waves"] += 1
                    stats["offers"] += len(offers)
                    continue
            if order.matching_alerted_at is None:
                # 3 to'lqindan keyin — adminga signal, employerga tanlov (TZ 7-bo'lim)
                order.matching_alerted_at = self.now
                stats["alerts"] += 1
                self.outbox.append(("matching_exhausted", (order.id,)))
        await self.db.flush()
        return stats
