"""Bekor qilish (employer va ishchi) va T−60 qisman to'lgan buyurtma tanlovi (TZ 6, 11).

WorkdayService dan meros: Ishonchlilik, almashtirish sloti va outbox bir xil ishlaydi.
"""

from datetime import timedelta

from sqlalchemy import func, select

from workly.domain.cancellation import (
    WORKER_MONTHLY_CANCEL_WARN,
    CancelTerms,
    CancelTier,
    employer_terms,
    shrink_price,
    worker_terms,
)
from workly.domain.errors import Forbidden, InvalidState, NotFound
from workly.domain.orders import (
    ACTIVE_STATUSES,
    AssignmentStatus,
    OfferStatus,
    OrderStatus,
    derive_workday_status,
    ensure_order_transition,
)
from workly.infrastructure.db.models import Offer, Order, ReliabilityEvent, User

from .audit import audit, record_transition
from .workday import WorkdayService, utc

CANCELLABLE = {AssignmentStatus.OPEN, AssignmentStatus.ASSIGNED, AssignmentStatus.ARRIVED, AssignmentStatus.WORKING}
ON_SITE = {AssignmentStatus.ARRIVED, AssignmentStatus.WORKING}


class CancellationService(WorkdayService):
    # ================= employer =================
    async def _own_order(self, user: User, order_id: int) -> Order:
        order = await self.db.get(Order, order_id)
        if order is None or order.employer_id != user.id:
            raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
        await self.db.refresh(order, attribute_names=["assignments"])
        return order

    def _employer_terms(self, order: Order) -> CancelTerms:
        workers = [a for a in order.assignments if a.worker_id and a.status in CANCELLABLE - {AssignmentStatus.OPEN}]
        on_site = [a for a in workers if a.status in ON_SITE]
        price = order.price["worker_price"]
        return employer_terms(
            utc(order.starts_at),
            self.now,
            has_workers=bool(workers),
            arrived=bool(on_site),
            order_total=price * order.days * len(workers),
            first_day_total=price * len(on_site),
        )

    async def employer_preview(self, user: User, order_id: int) -> CancelTerms:
        order = await self._own_order(user, order_id)
        if order.status not in ACTIVE_STATUSES:
            raise InvalidState("Buyurtma faol emas", code="INVALID_STATE")
        return self._employer_terms(order)

    async def cancel_order(self, user: User, order_id: int, reason: str | None) -> tuple[Order, CancelTerms]:
        order = await self._own_order(user, order_id)
        if order.status not in ACTIVE_STATUSES:
            raise InvalidState("Buyurtma faol emas", code="INVALID_STATE")
        terms = self._employer_terms(order)
        reason = (reason or "").strip() or None
        for a in order.assignments:
            if a.status in CANCELLABLE:
                had_worker = a.worker_id is not None
                self._set_status(a, AssignmentStatus.CANCELLED, user.id, reason="employer_cancel")
                if had_worker:
                    self.outbox.append(("workday_event", (a.id, "order_cancelled")))
        for offer in await self.db.scalars(
            select(Offer).where(Offer.order_id == order.id, Offer.status == OfferStatus.SENT)
        ):
            offer.status = OfferStatus.WITHDRAWN
        if terms.reliability:
            await self._reliability(user.id, "employer", terms.reliability, f"cancel_{terms.tier}", None)
        audit(
            self.db,
            user.id,
            "order.cancel",
            "order",
            order.id,
            after={"tier": terms.tier, "percent": terms.percent, "amount": terms.amount, "charged": terms.charged},
        )
        order.cancelled_at = self.now
        order.cancel_reason = reason
        await self.db.flush()
        # Allaqachon tugagan ishlar bo'lsa — buyurtma ular bo'yicha yakunlanadi
        done = derive_workday_status([a.status for a in order.assignments])
        new = done if done and done != OrderStatus.CANCELLED else OrderStatus.CANCELLED
        if new != order.status:
            if new == OrderStatus.CANCELLED:
                ensure_order_transition(order.status, new)
            record_transition(self.db, "order", order.id, order.status, new, user.id, reason=reason)
            order.status = new
        await self.db.flush()
        return order, terms

    # ================= ishchi =================
    async def _worker_terms(self, user: User, assignment_id: int):
        a = await self.for_worker(user, assignment_id)
        if a.status != AssignmentStatus.ASSIGNED:
            raise InvalidState("Ish boshlangan — bekor qilib bo'lmaydi", code="INVALID_STATE")
        starts_at = utc(a.order.starts_at)
        if self.now >= starts_at:
            raise InvalidState("Ish vaqti boshlangan — ish beruvchiga qo'ng'iroq qiling", code="CANCEL_TOO_LATE")
        return a, worker_terms(starts_at, self.now, a.order.price["worker_price"])

    async def worker_preview(self, user: User, assignment_id: int) -> CancelTerms:
        return (await self._worker_terms(user, assignment_id))[1]

    async def worker_cancel(self, user: User, assignment_id: int, reason: str | None):
        a, terms = await self._worker_terms(user, assignment_id)
        self._set_status(a, AssignmentStatus.CANCELLED, user.id, reason=(reason or "").strip()[:200] or "worker_cancel")
        # Bepul bekor ham hisoblanadi — oyiga 3+ marta ogohlantirish (TZ 11)
        await self._reliability(user.id, "worker", terms.reliability, f"cancel_{terms.tier}", a)
        audit(
            self.db,
            user.id,
            "assignment.worker_cancel",
            "assignment",
            a.id,
            after={"tier": terms.tier, "percent": terms.percent, "amount": terms.amount, "charged": terms.charged},
        )
        await self.db.flush()
        month = await self.db.scalar(
            select(func.count(ReliabilityEvent.id)).where(
                ReliabilityEvent.user_id == user.id,
                ReliabilityEvent.reason.like("cancel_%"),
                ReliabilityEvent.created_at >= self.now - timedelta(days=30),
            )
        )
        if terms.tier == CancelTier.FREE and (month or 0) >= WORKER_MONTHLY_CANCEL_WARN:
            self.outbox.append(("workday_event", (a.id, "cancel_warning")))
        await self._open_replacement(a, user.id, "worker_cancel")
        await self._sync_order(a.order, user.id)
        self.outbox.append(("order_event", (a.order_id, "worker_cancelled")))
        return a, terms

    # ================= T−60 tanlov =================
    async def partial_decision(self, user: User, order_id: int, start: bool) -> Order:
        """Employer: topilganlar bilan boshlash (qolgan o'rinlar yopiladi, narx kamayadi) yoki kutish."""
        order = await self._own_order(user, order_id)
        if order.status != OrderStatus.PARTIALLY_ASSIGNED:
            raise InvalidState("Buyurtma qisman to'lgan emas", code="INVALID_STATE")
        if order.partial_asked_at is None:
            raise Forbidden("Tanlov boshlanishdan 60 daqiqa oldin ochiladi", code="PARTIAL_NOT_ASKED")
        order.partial_decision = "start" if start else "wait"
        if start:
            close_open_slots(self, order, user.id, "employer_start_partial")
            for offer in await self.db.scalars(
                select(Offer).where(Offer.order_id == order.id, Offer.status == OfferStatus.SENT)
            ):
                offer.status = OfferStatus.WITHDRAWN
            await self._sync_order(order, user.id)
        audit(self.db, user.id, f"order.partial_{order.partial_decision}", "order", order.id)
        await self.db.flush()
        return order


def close_open_slots(svc: WorkdayService, order: Order, actor: int | None, reason: str) -> int:
    """Bo'sh o'rinlarni yopish va narxni topilgan ishchilar soniga tushirish ("qolgani qaytariladi")."""
    closed = 0
    for a in order.assignments:
        if a.status == AssignmentStatus.OPEN:
            svc._set_status(a, AssignmentStatus.CANCELLED, actor, reason=reason)
            closed += 1
    shrink_to_filled(order, closed)
    return closed


GONE = {AssignmentStatus.OPEN, AssignmentStatus.CANCELLED, AssignmentStatus.NO_SHOW, AssignmentStatus.REPLACED}


def shrink_to_filled(order: Order, closed: int) -> None:
    filled = sum(1 for a in order.assignments if a.worker_id and a.status not in GONE)
    if closed and filled:
        order.price = shrink_price(order.price, filled)
        order.workers_count = filled
