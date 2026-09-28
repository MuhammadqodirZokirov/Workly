from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field

from workly.domain.orders import PaymentMode, ToolsBy
from workly.domain.pricing import Duration, PriceUnit

from .schemas_worker import GeoPoint


class OrderIn(BaseModel):
    category_id: int
    specialization_id: int
    workers: int = Field(ge=1, le=50)
    date: date
    start_time: time
    duration: Duration | None = None  # kunlik ishlar uchun
    days: int = Field(default=1, ge=1, le=30)  # multi_day da
    volume: Decimal | None = Field(default=None, gt=0, le=100000)  # uy xizmatlari: m², mehmon, soat
    point: GeoPoint
    district_id: int
    address_text: str = Field(min_length=3, max_length=300)
    landmark: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    tools_by: ToolsBy = ToolsBy.EMPLOYER
    lunch: bool = False
    transport: bool = False
    top_only: bool = False
    payment_mode: PaymentMode = PaymentMode.CASH


class PriceOut(BaseModel):
    unit: PriceUnit
    worker_price: int
    days: int
    workers: int
    subtotal: int
    service_fee: int
    employer_total: int
    worker_net: int
    commission_enabled: bool


class QuoteOut(BaseModel):
    quote_id: str
    expires_at: datetime
    price: PriceOut
    night: bool
    needs_approval: bool
    cancellation_policy: list[str]


class OrderCreateIn(BaseModel):
    quote_id: str = Field(max_length=64)
    accept_rules: bool  # taqiqlangan ishlar ro'yxatiga rozilik (TZ 14)


class AssignmentOut(BaseModel):
    id: int
    slot_no: int
    worker_id: int | None
    status: str
    worker_name: str | None = None
    worker_phone: str | None = None
    arrived_at: datetime | None = None
    finished_at: datetime | None = None
    confirmed_at: datetime | None = None
    problem: str | None = None


class OrderOut(BaseModel):
    id: int
    status: str
    category_id: int
    specialization_id: int
    workers: int
    starts_at: datetime
    duration: Duration | None
    days: int
    volume: Decimal | None
    is_night: bool
    point: GeoPoint
    district_id: int
    address_text: str
    landmark: str | None
    description: str | None
    tools_by: ToolsBy
    lunch: bool
    transport: bool
    top_only: bool
    payment_mode: PaymentMode
    price: PriceOut
    assignments: list[AssignmentOut]
    created_at: datetime

    @classmethod
    def of(cls, o) -> "OrderOut":
        price = {k: v for k, v in o.price.items() if k in PriceOut.model_fields}
        return cls(
            id=o.id,
            status=o.status,
            category_id=o.category_id,
            specialization_id=o.specialization_id,
            workers=o.workers_count,
            starts_at=o.starts_at,
            duration=o.duration,
            days=o.days,
            volume=Decimal(o.volume) if o.volume else None,
            is_night=o.is_night,
            point=GeoPoint(lat=o.lat, lon=o.lon),
            district_id=o.district_id,
            address_text=o.address_text,
            landmark=o.landmark,
            description=o.description,
            tools_by=o.tools_by,
            lunch=o.lunch,
            transport=o.transport,
            top_only=o.top_only,
            payment_mode=o.payment_mode,
            price=PriceOut(**price),
            assignments=[
                AssignmentOut(
                    id=a.id,
                    slot_no=a.slot_no,
                    worker_id=a.worker_id,
                    status=a.status,
                    arrived_at=a.arrived_at,
                    finished_at=a.finished_at,
                    confirmed_at=a.confirmed_at,
                    problem=a.problem,
                )
                for a in o.assignments
            ],
            created_at=o.created_at,
        )


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class RepeatIn(BaseModel):
    date: date
    start_time: time | None = None


class PriceConfigIn(BaseModel):
    category_id: int
    specialization_id: int | None = None
    unit: PriceUnit
    base: int = Field(gt=0, le=100_000_000)
    min_price: int | None = Field(default=None, gt=0)
    max_price: int | None = Field(default=None, gt=0)
    min_order_amount: int = Field(default=0, ge=0)


class PriceConfigOut(PriceConfigIn):
    id: int
    min_price: int
    max_price: int
    active_from: datetime
