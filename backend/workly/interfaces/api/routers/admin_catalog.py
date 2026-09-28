from fastapi import APIRouter, Depends, Request

from workly.application.orders import OrderService
from workly.application.pricing import PriceService
from workly.domain.users import Role
from workly.infrastructure.db.models import User

from ..deps import DbDep, RedisDep, SettingsDep, client_ip, require_roles
from ..schemas_orders import OrderOut, PriceConfigIn, PriceConfigOut

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_roles(Role.ADMIN, mfa=True)


def _out(r) -> PriceConfigOut:
    return PriceConfigOut(
        id=r.id,
        category_id=r.category_id,
        specialization_id=r.specialization_id,
        unit=r.unit,
        base=r.base,
        min_price=r.min_price,
        max_price=r.max_price,
        min_order_amount=r.min_order_amount,
        active_from=r.active_from,
    )


@router.get("/prices", response_model=list[PriceConfigOut], dependencies=[Depends(_admin)])
async def prices(db: DbDep):
    return [_out(r) for r in await PriceService(db).current()]


@router.post("/prices", response_model=PriceConfigOut, status_code=201)
async def set_price(body: PriceConfigIn, db: DbDep, request: Request, admin: User = Depends(_admin)):
    """Yangi narx versiyasi; faqat yangi buyurtmalarga ta'sir qiladi (TZ 8, 16-bo'limlar)."""
    row = await PriceService(db).set_price(
        admin,
        category_id=body.category_id,
        specialization_id=body.specialization_id,
        unit=body.unit,
        base=body.base,
        min_price=body.min_price,
        max_price=body.max_price,
        min_order_amount=body.min_order_amount,
        ip=client_ip(request),
    )
    return _out(row)


@router.post("/orders/{order_id}/approve", response_model=OrderOut)
async def approve_order(
    order_id: int, db: DbDep, redis: RedisDep, settings: SettingsDep, admin: User = Depends(_admin)
):
    """Yangi employerning 10+ ishchili buyurtmasini tasdiqlash (TZ 5-bo'lim)."""
    return OrderOut.of(await OrderService(db, redis, settings).approve(admin, order_id))
