from fastapi import APIRouter, Header, Query

from workly.application.orders import OrderParams, OrderService, QuoteResult
from workly.domain.orders import OrderStatus

from ..deps import CurrentUser, DbDep, RedisDep, SettingsDep
from ..schemas_orders import CancelIn, OrderCreateIn, OrderIn, OrderOut, PriceOut, QuoteOut, RepeatIn

router = APIRouter(prefix="/orders", tags=["orders"])

# Bekor qilish qoidalari narx ekranida ko'rsatiladi (TZ 11-bo'lim)
CANCELLATION_POLICY = [
    "Ishchi tayinlanmagan yoki ishdan ≥ 24 soat oldin — bepul",
    "6–24 soat oldin — buyurtmaning 20% i ishchilarga",
    "6 soatdan kam qolganda — 50%",
    "Ishchi yetib kelgandan keyin — birinchi kunning 100%",
]


def _params(b: OrderIn) -> OrderParams:
    return OrderParams(
        category_id=b.category_id,
        specialization_id=b.specialization_id,
        workers=b.workers,
        date=b.date,
        start_time=b.start_time,
        duration=b.duration,
        days=b.days,
        volume=b.volume,
        lat=b.point.lat,
        lon=b.point.lon,
        district_id=b.district_id,
        address_text=b.address_text,
        landmark=b.landmark,
        description=b.description,
        tools_by=b.tools_by,
        lunch=b.lunch,
        transport=b.transport,
        top_only=b.top_only,
        payment_mode=b.payment_mode,
    )


def _quote_out(r: QuoteResult) -> QuoteOut:
    q = r.quote
    return QuoteOut(
        quote_id=r.quote_id,
        expires_at=r.expires_at,
        night=r.night,
        needs_approval=r.needs_approval,
        price=PriceOut(
            unit=q.unit,
            worker_price=q.worker_price,
            days=q.days,
            workers=q.workers,
            subtotal=q.subtotal,
            service_fee=q.service_fee,
            employer_total=q.employer_total,
            worker_net=q.worker_net,
            commission_enabled=q.commission_enabled,
        ),
        cancellation_policy=CANCELLATION_POLICY,
    )


@router.post("/quote", response_model=QuoteOut)
async def quote(body: OrderIn, user: CurrentUser, db: DbDep, redis: RedisDep, settings: SettingsDep):
    return _quote_out(await OrderService(db, redis, settings).quote(user, _params(body)))


@router.post("", response_model=OrderOut, status_code=201)
async def create(
    body: OrderCreateIn,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    settings: SettingsDep,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=64),
):
    order = await OrderService(db, redis, settings).create(user, body.quote_id, idempotency_key, body.accept_rules)
    return OrderOut.of(order)


@router.get("", response_model=list[OrderOut])
async def list_orders(
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    settings: SettingsDep,
    status: OrderStatus | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return [OrderOut.of(o) for o in await OrderService(db, redis, settings).list_own(user, status, limit, offset)]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, user: CurrentUser, db: DbDep, redis: RedisDep, settings: SettingsDep):
    return OrderOut.of(await OrderService(db, redis, settings).get(user, order_id))


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel(order_id: int, body: CancelIn, user: CurrentUser, db: DbDep, redis: RedisDep, settings: SettingsDep):
    return OrderOut.of(await OrderService(db, redis, settings).cancel(user, order_id, body.reason))


@router.post("/{order_id}/repeat", response_model=QuoteOut)
async def repeat(order_id: int, body: RepeatIn, user: CurrentUser, db: DbDep, redis: RedisDep, settings: SettingsDep):
    """Oldingi parametrlar bilan yangi narx; tasdiqlash — POST /orders."""
    svc = OrderService(db, redis, settings)
    params = await svc.repeat_params(user, order_id, body.date, body.start_time)
    return _quote_out(await svc.quote(user, params))
