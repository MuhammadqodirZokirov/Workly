"""Buyurtma: narx hisobi (15 daqiqa blok), yaratish, ro'yxat, bekor qilish (TZ 5, 6-bo'limlar)."""

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Conflict, Forbidden, InvalidState, NotFound, ValidationFailed
from workly.domain.orders import (
    ACTIVE_STATUSES,
    FIRST_ORDER_MAX_WORKERS,
    NEW_EMPLOYER_APPROVAL_FROM,
    QUOTE_TTL_SECONDS,
    AssignmentStatus,
    OrderStatus,
    PaymentMode,
    ToolsBy,
    check_description,
    ensure_order_transition,
    is_night,
    validate_start,
)
from workly.domain.pricing import Duration, PriceUnit, Quote, QuoteInput, calculate
from workly.domain.users import Role
from workly.infrastructure.config import Settings
from workly.infrastructure.db.models import (
    Assignment,
    Category,
    District,
    EmployerProfile,
    Order,
    Region,
    Specialization,
    User,
)

from .audit import record_transition
from .pricing import PriceService

TASHKENT = ZoneInfo("Asia/Tashkent")
IDEMPOTENCY_TTL = 24 * 3600


@dataclass
class OrderParams:
    category_id: int
    specialization_id: int
    workers: int
    date: date
    start_time: time
    duration: Duration | None
    days: int
    volume: Decimal | None
    lat: float
    lon: float
    district_id: int
    address_text: str
    landmark: str | None
    description: str | None
    tools_by: ToolsBy
    lunch: bool
    transport: bool
    top_only: bool
    payment_mode: PaymentMode = PaymentMode.CASH

    @property
    def starts_at(self) -> datetime:
        return datetime.combine(self.date, self.start_time, TASHKENT).astimezone(UTC)

    def to_json(self) -> dict:
        d = asdict(self)
        d.update(
            date=self.date.isoformat(),
            start_time=self.start_time.isoformat(),
            volume=str(self.volume) if self.volume is not None else None,
        )
        return d

    @classmethod
    def from_json(cls, d: dict) -> "OrderParams":
        d = dict(d)
        d.update(
            date=date.fromisoformat(d["date"]),
            start_time=time.fromisoformat(d["start_time"]),
            volume=Decimal(d["volume"]) if d["volume"] is not None else None,
            duration=Duration(d["duration"]) if d["duration"] else None,
            tools_by=ToolsBy(d["tools_by"]),
            payment_mode=PaymentMode(d["payment_mode"]),
        )
        return cls(**d)


@dataclass
class QuoteResult:
    quote_id: str
    expires_at: datetime
    params: OrderParams
    quote: Quote
    night: bool
    needs_approval: bool


def _quote_to_json(q: Quote) -> dict:
    return asdict(q)


def _quote_from_json(d: dict) -> Quote:
    return Quote(**{**d, "unit": PriceUnit(d["unit"])})


class OrderService:
    def __init__(self, db: AsyncSession, redis: Redis, settings: Settings):
        self.db, self.redis, self.settings = db, redis, settings

    # ---------- tekshiruvlar ----------
    async def _ensure_employer(self, user: User) -> None:
        if Role.EMPLOYER not in user.role_names:
            raise Forbidden("Avval ish beruvchi rolini qo'shing", code="NOT_AN_EMPLOYER")
        if user.phone_verified_at is None:
            raise Forbidden("Telefon raqam tasdiqlanmagan", code="PHONE_NOT_VERIFIED")
        if await self.db.get(EmployerProfile, user.id) is None:
            self.db.add(EmployerProfile(user_id=user.id, type="individual"))
            await self.db.flush()

    async def _validate(self, user: User, p: OrderParams) -> tuple[bool, bool]:
        spec = await self.db.get(Specialization, p.specialization_id)
        cat = await self.db.get(Category, p.category_id)
        if cat is None or not cat.is_active:
            raise ValidationFailed("Kategoriya topilmadi yoki faol emas", code="INVALID_CATEGORY")
        if spec is None or not spec.is_active or spec.category_id != cat.id:
            raise ValidationFailed("Mutaxassislik bu kategoriyaga tegishli emas", code="INVALID_SPECIALIZATION")
        district = await self.db.scalar(
            select(District.id)
            .join(Region)
            .where(District.id == p.district_id, District.is_active.is_(True), Region.is_active.is_(True))
        )
        if district is None:
            raise ValidationFailed("Bu hududda hozircha xizmat yo'q", code="INVALID_DISTRICT")
        if not p.address_text.strip():
            raise ValidationFailed("Manzilni kiriting", code="ADDRESS_REQUIRED")
        if p.payment_mode != PaymentMode.CASH:
            raise ValidationFailed("Onlayn to'lov Faza 2 da", code="PAYMENT_MODE_UNAVAILABLE")
        validate_start(p.starts_at, datetime.now(UTC))
        check_description(p.description)

        previous = await self.db.scalar(
            select(func.count(Order.id)).where(
                Order.employer_id == user.id, Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.EXPIRED])
            )
        )
        if previous == 0 and p.workers > FIRST_ORDER_MAX_WORKERS:
            raise ValidationFailed(
                f"Birinchi buyurtmada ko'pi bilan {FIRST_ORDER_MAX_WORKERS} ta ishchi", code="FIRST_ORDER_LIMIT"
            )
        completed = await self.db.scalar(
            select(func.count(Order.id)).where(Order.employer_id == user.id, Order.status == OrderStatus.COMPLETED)
        )
        needs_approval = completed == 0 and p.workers >= NEW_EMPLOYER_APPROVAL_FROM
        return is_night(p.start_time), needs_approval

    # ---------- narx ----------
    async def quote(self, user: User, p: OrderParams) -> QuoteResult:
        await self._ensure_employer(user)
        night, needs_approval = await self._validate(user, p)
        row, cfg = await PriceService(self.db).resolve(p.category_id, p.specialization_id)
        q = calculate(
            cfg,
            QuoteInput(
                workers=p.workers,
                duration=p.duration,
                days=p.days,
                volume=p.volume,
                worker_tools=p.tools_by == ToolsBy.WORKER,
                top_only=p.top_only,
            ),
            commission_enabled=self.settings.commission_enabled,
        )
        if cfg.unit == PriceUnit.DAY:
            p.volume = None
            p.days = q.days
        else:
            p.duration, p.days = None, 1
        quote_id = secrets.token_urlsafe(16)
        payload = {"user_id": user.id, "params": p.to_json(), "quote": _quote_to_json(q), "price_config_id": row.id}
        await self.redis.set(f"quote:{quote_id}", json.dumps(payload), ex=QUOTE_TTL_SECONDS)
        expires = datetime.now(UTC).timestamp() + QUOTE_TTL_SECONDS
        return QuoteResult(quote_id, datetime.fromtimestamp(expires, UTC), p, q, night, needs_approval)

    # ---------- yaratish ----------
    async def create(self, user: User, quote_id: str, idempotency_key: str, accept_rules: bool) -> Order:
        if not accept_rules:
            raise ValidationFailed("Taqiqlangan ishlar ro'yxatiga rozilik kerak", code="RULES_NOT_ACCEPTED")
        idem = f"idem:orders:{user.id}:{idempotency_key}"
        if not await self.redis.set(idem, "pending", ex=IDEMPOTENCY_TTL, nx=True):
            value = await self.redis.get(idem)
            value = value.decode() if isinstance(value, bytes) else value
            if value == "pending":
                raise Conflict("Bu so'rov allaqachon bajarilmoqda", code="IDEMPOTENCY_IN_PROGRESS")
            if value and (order := await self.db.get(Order, int(value))) is not None:
                return order  # takroriy so'rov — o'sha buyurtma qaytadi
            # yozuv bor, lekin buyurtma yo'q (commit bo'lmagan) — qaytadan yaratamiz
            await self.redis.set(idem, "pending", ex=IDEMPOTENCY_TTL)
        try:
            order = await self._create(user, quote_id)
        except Exception:
            await self.redis.delete(idem)
            raise
        await self.redis.set(idem, str(order.id), ex=IDEMPOTENCY_TTL)
        return order

    async def _create(self, user: User, quote_id: str) -> Order:
        await self._ensure_employer(user)
        raw = await self.redis.get(f"quote:{quote_id}")
        if raw is None:
            raise ValidationFailed("Narx muddati tugadi, qayta hisoblang", code="QUOTE_EXPIRED")
        payload = json.loads(raw)
        if payload["user_id"] != user.id:
            raise ValidationFailed("Narx topilmadi", code="QUOTE_EXPIRED")
        p = OrderParams.from_json(payload["params"])
        night, needs_approval = await self._validate(user, p)  # vaqt o'tgan bo'lishi mumkin — qayta tekshiramiz
        quote = payload["quote"]

        status = OrderStatus.PENDING_APPROVAL if needs_approval else OrderStatus.MATCHING
        order = Order(
            employer_id=user.id,
            category_id=p.category_id,
            specialization_id=p.specialization_id,
            workers_count=p.workers,
            starts_at=p.starts_at,
            duration=p.duration,
            days=p.days,
            volume=str(p.volume) if p.volume is not None else None,
            is_night=night,
            lat=p.lat,
            lon=p.lon,
            district_id=p.district_id,
            address_text=" ".join(p.address_text.split()),
            landmark=(p.landmark or "").strip() or None,
            description=(p.description or "").strip() or None,
            tools_by=p.tools_by,
            lunch=p.lunch,
            transport=p.transport,
            top_only=p.top_only,
            payment_mode=p.payment_mode,
            price={**quote, "price_config_id": payload["price_config_id"]},
            status=status,
            assignments=[Assignment(slot_no=i + 1, status=AssignmentStatus.OPEN) for i in range(p.workers)],
        )
        self.db.add(order)
        await self.db.flush()
        record_transition(self.db, "order", order.id, None, status, user.id)
        await self.redis.delete(f"quote:{quote_id}")  # narx bir marta ishlatiladi
        return order

    # ---------- o'qish ----------
    async def list_own(self, user: User, status: OrderStatus | None, limit: int, offset: int) -> list[Order]:
        q = select(Order).where(Order.employer_id == user.id)
        if status:
            q = q.where(Order.status == status)
        return list(
            await self.db.scalars(q.order_by(Order.starts_at.desc(), Order.id.desc()).limit(limit).offset(offset))
        )

    async def get(self, user: User, order_id: int) -> Order:
        order = await self.db.get(Order, order_id)
        staff = {Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN} & set(user.role_names)
        if order is None or (order.employer_id != user.id and not staff):
            raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
        return order

    async def repeat_params(self, user: User, order_id: int, new_date: date, new_time: time | None) -> OrderParams:
        o = await self.get(user, order_id)
        if o.employer_id != user.id:
            raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
        local = o.starts_at if o.starts_at.tzinfo else o.starts_at.replace(tzinfo=UTC)
        return OrderParams(
            category_id=o.category_id,
            specialization_id=o.specialization_id,
            workers=o.workers_count,
            date=new_date,
            start_time=new_time or local.astimezone(TASHKENT).time(),
            duration=Duration(o.duration) if o.duration else None,
            days=o.days,
            volume=Decimal(o.volume) if o.volume else None,
            lat=o.lat,
            lon=o.lon,
            district_id=o.district_id,
            address_text=o.address_text,
            landmark=o.landmark,
            description=o.description,
            tools_by=ToolsBy(o.tools_by),
            lunch=o.lunch,
            transport=o.transport,
            top_only=o.top_only,
        )

    # ---------- bekor qilish ----------
    async def cancel(self, user: User, order_id: int, reason: str | None) -> Order:
        order = await self.get(user, order_id)
        if order.employer_id != user.id:
            raise Forbidden()
        if order.status not in ACTIVE_STATUSES:
            raise InvalidState("Buyurtma faol emas", code="INVALID_STATE")
        if any(a.status != AssignmentStatus.OPEN for a in order.assignments):
            # TODO(matching): tayinlangan ishchi bo'lsa — 11-bo'limdagi to'lov jadvali bilan
            raise InvalidState(
                "Ishchi tayinlangan buyurtmani bekor qilish keyingi bosqichda qo'shiladi", code="CANCEL_WITH_ASSIGNED"
            )
        ensure_order_transition(order.status, OrderStatus.CANCELLED)
        old = order.status
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now(UTC)
        order.cancel_reason = (reason or "").strip() or None
        for a in order.assignments:
            a.status = AssignmentStatus.CANCELLED
        record_transition(self.db, "order", order.id, old, OrderStatus.CANCELLED, user.id, reason=order.cancel_reason)
        await self.db.flush()
        return order

    async def approve(self, admin: User, order_id: int) -> Order:
        order = await self.db.get(Order, order_id)
        if order is None:
            raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
        ensure_order_transition(order.status, OrderStatus.MATCHING)
        record_transition(self.db, "order", order.id, order.status, OrderStatus.MATCHING, admin.id)
        order.status = OrderStatus.MATCHING
        await self.db.flush()
        return order
