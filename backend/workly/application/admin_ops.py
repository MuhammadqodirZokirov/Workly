"""Admin: operatsiya taxtasi, qo'ng'iroq navbati, buyurtmalar, nizolar, foydalanuvchilar (TZ 16, 12).

Faza 1-lite: nizo — admin qo'lda hal qiladi (naqd rejim: pul ko'chirilmaydi, qaror Ishonchlilik,
bloklar va ish holati orqali bajariladi). Har harakat audit jurnaliga yoziladi.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import InvalidState, NotFound, ValidationFailed
from workly.domain.names import public_name
from workly.domain.orders import ACTIVE_STATUSES, MATCHING_STATUSES, AssignmentStatus, OfferStatus, OrderStatus
from workly.domain.users import UserStatus
from workly.domain.workday import LATE_ESCALATE
from workly.domain.worker import VerificationStatus
from workly.infrastructure.db.models import (
    Assignment,
    AuditLog,
    EmployerProfile,
    Offer,
    Order,
    StateTransition,
    User,
    WorkerProfile,
)

from .audit import audit, record_transition
from .matching import MatchingService
from .notifications import Notifier
from .workday import WorkdayService, utc

TASHKENT = ZoneInfo("Asia/Tashkent")
UNFOUNDED_DISPUTE_PENALTY = -10  # asossiz nizo ochgan tomonga (TZ 12)
MIN_REASON = 10


@dataclass
class CallItem:
    assignment_id: int
    order_id: int
    starts_at: datetime
    minutes_late: int
    worker_id: int | None
    worker_name: str | None
    worker_phone: str | None
    employer_phone: str | None
    address_text: str


@dataclass
class ProblemItem:
    assignment_id: int
    order_id: int
    worker_name: str | None
    problem: str | None
    since: datetime | None


@dataclass
class Board:
    date: str
    orders: dict[str, int] = field(default_factory=dict)
    assignments: dict[str, int] = field(default_factory=dict)
    pending: dict[str, int] = field(default_factory=dict)
    call_queue: list[CallItem] = field(default_factory=list)
    problems: list[ProblemItem] = field(default_factory=list)
    unfilled: list[int] = field(default_factory=list)  # 3 to'lqindan keyin to'lmagan buyurtmalar


def today_bounds(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(TASHKENT).date()
    start = datetime.combine(local, time.min, TASHKENT).astimezone(UTC)
    return start, start + timedelta(days=1)


class AdminOpsService(WorkdayService):
    """WorkdayService dan meros: holat o'tishlari, Ishonchlilik va outbox bir xil ishlaydi."""

    def __init__(self, db: AsyncSession, now: datetime | None = None):
        super().__init__(db, None, now)

    async def _names(self, user_id: int | None) -> tuple[str | None, str | None]:
        if user_id is None:
            return None, None
        user = await self.db.get(User, user_id)
        profile = await self.db.get(WorkerProfile, user_id)
        name = public_name(profile.first_name, profile.last_name) if profile else (user.full_name if user else None)
        return name, user.phone if user else None

    # ================= operatsiya taxtasi =================
    async def board(self) -> Board:
        start, end = today_bounds(self.now)
        board = Board(date=start.astimezone(TASHKENT).date().isoformat())
        rows = await self.db.execute(
            select(Order.status, func.count(Order.id))
            .where(Order.starts_at >= start, Order.starts_at < end)
            .group_by(Order.status)
        )
        board.orders = {s: n for s, n in rows}
        rows = await self.db.execute(
            select(Assignment.status, func.count(Assignment.id))
            .join(Order, Order.id == Assignment.order_id)
            .where(Order.starts_at >= start, Order.starts_at < end, Assignment.worker_id.is_not(None))
            .group_by(Assignment.status)
        )
        board.assignments = {s: n for s, n in rows}
        board.pending = {
            "verifications": await self.db.scalar(
                select(func.count())
                .select_from(WorkerProfile)
                .where(WorkerProfile.verification_status == VerificationStatus.PENDING)
            )
            or 0,
            "business": await self.db.scalar(
                select(func.count()).select_from(EmployerProfile).where(EmployerProfile.business_status == "pending")
            )
            or 0,
            "orders_approval": await self.db.scalar(
                select(func.count()).select_from(Order).where(Order.status == OrderStatus.PENDING_APPROVAL)
            )
            or 0,
            "disputes": await self.db.scalar(
                select(func.count()).select_from(Assignment).where(Assignment.status == AssignmentStatus.DISPUTED)
            )
            or 0,
        }
        board.call_queue = await self.call_queue()
        board.problems = await self.problems()
        board.unfilled = list(
            await self.db.scalars(
                select(Order.id).where(
                    Order.status.in_(MATCHING_STATUSES),
                    Order.matching_alerted_at.is_not(None),
                    Order.starts_at > self.now,
                )
            )
        )
        return board

    async def call_queue(self) -> list[CallItem]:
        """T+30: ishchi kelmadi — qo'ng'iroq qilish vazifasi (SLA ≤ 10 daqiqa, TZ 16)."""
        rows = await self.db.scalars(
            select(Assignment)
            .join(Order, Order.id == Assignment.order_id)
            .where(Assignment.status == AssignmentStatus.ASSIGNED, Order.starts_at <= self.now - LATE_ESCALATE)
            .order_by(Order.starts_at)
        )
        out = []
        for a in rows:
            if (a.timeline or {}).get("called_at"):
                continue
            await self.db.refresh(a, attribute_names=["order"])
            worker_name, worker_phone = await self._names(a.worker_id)
            employer = await self.db.get(User, a.order.employer_id)
            out.append(
                CallItem(
                    assignment_id=a.id,
                    order_id=a.order_id,
                    starts_at=a.order.starts_at,
                    minutes_late=int((self.now - utc(a.order.starts_at)).total_seconds() // 60),
                    worker_id=a.worker_id,
                    worker_name=worker_name,
                    worker_phone=worker_phone,
                    employer_phone=employer.phone if employer else None,
                    address_text=a.order.address_text,
                )
            )
        return out

    async def mark_called(self, admin: User, assignment_id: int, note: str | None) -> Assignment:
        a = await self._assignment(assignment_id)
        tl = dict(a.timeline or {})
        tl["called_at"] = self.now.isoformat()
        tl["call_note"] = (note or "").strip()[:300] or None
        a.timeline = tl
        audit(self.db, admin.id, "ops.call_done", "assignment", a.id, after={"note": tl["call_note"]})
        await self.db.flush()
        return a

    async def problems(self) -> list[ProblemItem]:
        rows = await self.db.scalars(
            select(Assignment).where(Assignment.status == AssignmentStatus.DISPUTED).order_by(Assignment.id)
        )
        out = []
        for a in rows:
            since = await self.db.scalar(
                select(func.max(StateTransition.created_at)).where(
                    StateTransition.object_type == "assignment",
                    StateTransition.object_id == a.id,
                    StateTransition.to_state == AssignmentStatus.DISPUTED,
                )
            )
            out.append(ProblemItem(a.id, a.order_id, (await self._names(a.worker_id))[0], a.problem, since))
        return out

    # ================= nizolar =================
    async def resolve_dispute(
        self, admin: User, assignment_id: int, *, confirm: bool, reason: str, unfounded: str | None
    ) -> Assignment:
        """Qaror: ish hisoblanadi (confirm) yoki yo'q; asossiz nizo ochgan tomonga −10 (TZ 12)."""
        a = await self._assignment(assignment_id)
        if a.status != AssignmentStatus.DISPUTED:
            raise InvalidState("Bu tayinlovda nizo yo'q", code="INVALID_STATE")
        reason = (reason or "").strip()
        if len(reason) < MIN_REASON:
            raise ValidationFailed("Qaror sababini yozing (kamida 10 belgi)", code="REASON_REQUIRED")
        if unfounded not in (None, "worker", "employer"):
            raise ValidationFailed("unfounded: worker, employer yoki bo'sh", code="INVALID_SIDE")
        tl = dict(a.timeline or {})
        tl["resolution"] = {
            "confirm": confirm,
            "reason": reason,
            "unfounded": unfounded,
            "by": admin.id,
            "at": self.now.isoformat(),
        }
        a.timeline = tl
        if confirm:
            await self._confirm(a, admin.id, auto=False)
        else:
            self._set_status(a, AssignmentStatus.CANCELLED, admin.id, reason="dispute_rejected")
            if a.finished_at is None:
                # Ish boshlanmay turib nizo (masalan, boshqa odam keldi) — o'rniga yangi ishchi izlanadi
                await self._open_replacement(a, admin.id, "dispute_replacement")
        if unfounded:
            target = a.worker_id if unfounded == "worker" else a.order.employer_id
            await self._reliability(target, unfounded, UNFOUNDED_DISPUTE_PENALTY, "unfounded_dispute", a)
        audit(self.db, admin.id, "dispute.resolve", "assignment", a.id, after=tl["resolution"])
        await self._sync_order(a.order, admin.id)
        self.outbox.append(("workday_event", (a.id, "dispute_resolved")))
        return a

    # ================= buyurtmalar =================
    async def orders(self, status: str | None, q: str | None, day: str | None, limit: int, offset: int) -> list[Order]:
        stmt = select(Order).order_by(Order.starts_at.desc())
        if status:
            stmt = stmt.where(Order.status == status)
        if day:
            start, end = today_bounds(datetime.combine(datetime.fromisoformat(day).date(), time(12), TASHKENT))
            stmt = stmt.where(Order.starts_at >= start, Order.starts_at < end)
        if q:
            q = q.strip()
            if q.lstrip("#").isdigit() and len(q.lstrip("#")) < 9:
                stmt = stmt.where(Order.id == int(q.lstrip("#")))
            else:
                digits = "".join(ch for ch in q if ch.isdigit())
                users = select(User.id).where(User.phone.like(f"%{digits[-9:]}%")) if digits else None
                if users is None:
                    return []
                stmt = stmt.where(
                    or_(
                        Order.employer_id.in_(users),
                        Order.id.in_(select(Assignment.order_id).where(Assignment.worker_id.in_(users))),
                    )
                )
        return list(await self.db.scalars(stmt.limit(limit).offset(offset)))

    async def order_timeline(self, order: Order) -> list[StateTransition]:
        ids = [a.id for a in order.assignments]
        rows = await self.db.scalars(
            select(StateTransition)
            .where(
                or_(
                    (StateTransition.object_type == "order") & (StateTransition.object_id == order.id),
                    (StateTransition.object_type == "assignment") & (StateTransition.object_id.in_(ids or [-1])),
                )
            )
            .order_by(StateTransition.created_at, StateTransition.id)
        )
        return list(rows)

    async def admin_cancel(self, admin: User, order_id: int, reason: str) -> Order:
        """Admin bekor qiladi — tomonlarga jarima yo'q (masalan, firibgarlik yoki texnik sabab)."""
        order = await self.db.get(Order, order_id)
        if order is None:
            raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
        if order.status not in ACTIVE_STATUSES:
            raise InvalidState("Buyurtma faol emas", code="INVALID_STATE")
        reason = (reason or "").strip()
        if len(reason) < MIN_REASON:
            raise ValidationFailed("Sababini yozing (kamida 10 belgi)", code="REASON_REQUIRED")
        await self.db.refresh(order, attribute_names=["assignments"])
        for a in order.assignments:
            if a.status in (
                AssignmentStatus.OPEN,
                AssignmentStatus.ASSIGNED,
                AssignmentStatus.ARRIVED,
                AssignmentStatus.WORKING,
            ):
                if a.worker_id:
                    self.outbox.append(("workday_event", (a.id, "order_cancelled")))
                self._set_status(a, AssignmentStatus.CANCELLED, admin.id, reason="admin_cancel")
        for offer in await self.db.scalars(
            select(Offer).where(Offer.order_id == order.id, Offer.status == OfferStatus.SENT)
        ):
            offer.status = OfferStatus.WITHDRAWN
        record_transition(self.db, "order", order.id, order.status, OrderStatus.CANCELLED, admin.id, reason=reason)
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = self.now
        order.cancel_reason = reason
        audit(self.db, admin.id, "admin.order_cancel", "order", order.id, after={"reason": reason})
        self.outbox.append(("order_event", (order.id, "cancelled_by_admin")))
        await self.db.flush()
        return order

    async def manual_assign(self, admin: User, order_id: int, worker_id: int, redis: Redis, notifier: Notifier):
        """Qo'lda tayinlash: vaqt to'qnashuvi va slot qoidalari matching bilan bir xil tekshiriladi."""
        order = await self.db.get(Order, order_id)
        if order is None:
            raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
        profile = await self.db.get(WorkerProfile, worker_id)
        worker = await self.db.get(User, worker_id)
        if profile is None or worker is None or profile.verification_status != VerificationStatus.VERIFIED:
            raise InvalidState("Ishchi tasdiqlanmagan", code="WORKER_NOT_VERIFIED")
        if worker.status != UserStatus.ACTIVE:
            raise InvalidState("Ishchi bloklangan", code="WORKER_BLOCKED")
        matching = MatchingService(self.db, redis, notifier, now=self.now)
        offer = Offer(
            order_id=order.id,
            worker_id=worker_id,
            wave=0,
            status=OfferStatus.SENT,
            sent_at=self.now,
            expires_at=self.now + timedelta(minutes=1),
        )
        self.db.add(offer)
        await self.db.flush()
        slot = await matching._assign(offer, profile)
        audit(self.db, admin.id, "admin.manual_assign", "assignment", slot.id, after={"worker_id": worker_id})
        matching.outbox.append(("worker_assigned", (offer.id,)))
        return slot, matching

    # ================= foydalanuvchilar =================
    async def users(self, q: str, limit: int = 20) -> list[User]:
        q = (q or "").strip()
        if not q:
            return []
        conds = []
        digits = "".join(ch for ch in q if ch.isdigit())
        if q.isdigit() and len(q) < 9:
            conds.append(User.id == int(q))
        if len(digits) >= 4:
            conds.append(User.phone.like(f"%{digits[-9:]}%"))
        if not q.isdigit():
            conds.append(User.full_name.ilike(f"%{q}%"))
        return list(await self.db.scalars(select(User).where(or_(*conds)).order_by(User.id).limit(limit)))

    async def set_blocked(self, admin: User, user_id: int, blocked: bool, reason: str) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFound("Foydalanuvchi topilmadi", code="USER_NOT_FOUND")
        reason = (reason or "").strip()
        if len(reason) < MIN_REASON:
            raise ValidationFailed("Sababini yozing (kamida 10 belgi)", code="REASON_REQUIRED")
        if user.id == admin.id:
            raise InvalidState("O'zingizni bloklay olmaysiz", code="SELF_BLOCK")
        before = user.status
        user.status = UserStatus.BLOCKED if blocked else UserStatus.ACTIVE
        audit(
            self.db,
            admin.id,
            "user.block" if blocked else "user.unblock",
            "user",
            user.id,
            before={"status": before},
            after={"status": user.status, "reason": reason},
        )
        await self.db.flush()
        return user

    async def user_history(self, user_id: int, limit: int = 30) -> list[AuditLog]:
        rows = await self.db.scalars(
            select(AuditLog)
            .where(AuditLog.object_type == "user", AuditLog.object_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(rows)
