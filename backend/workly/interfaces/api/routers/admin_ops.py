"""Admin panel: operatsiya taxtasi (moderator ham), buyurtmalar, nizolar, foydalanuvchilar (faqat admin)."""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from pydantic import BaseModel, Field

from workly.application.admin_ops import AdminOpsService
from workly.domain.errors import NotFound
from workly.domain.names import public_name
from workly.domain.users import Role
from workly.infrastructure.db.models import EmployerProfile, Order, User, WorkerProfile
from workly.workers.scheduler import deliver_workday_outbox

from ..deps import DbDep, Moderator, NotifierDep, RedisDep, require_roles
from ..schemas_orders import OrderOut
from .orders import _order_out

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_roles(Role.ADMIN, mfa=True)


# ---------------- sxemalar ----------------
class CallItemOut(BaseModel):
    assignment_id: int
    order_id: int
    starts_at: datetime
    minutes_late: int
    worker_id: int | None
    worker_name: str | None
    worker_phone: str | None
    employer_phone: str | None
    address_text: str


class ProblemOut(BaseModel):
    assignment_id: int
    order_id: int
    worker_name: str | None
    problem: str | None
    since: datetime | None


class BoardOut(BaseModel):
    date: str
    orders: dict[str, int]
    assignments: dict[str, int]
    pending: dict[str, int]
    call_queue: list[CallItemOut]
    problems: list[ProblemOut]
    unfilled: list[int]


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class ResolveIn(BaseModel):
    confirm: bool  # ish hisoblanadimi
    reason: str = Field(min_length=1, max_length=500)
    unfounded: str | None = None  # "worker" | "employer" — asossiz nizo ochgan tomon (−10)


class AssignIn(BaseModel):
    worker_id: int


class TransitionOut(BaseModel):
    object_type: str
    object_id: int
    from_state: str | None
    to_state: str
    actor_id: int | None
    reason: str | None
    created_at: datetime


class AdminOrderOut(BaseModel):
    order: OrderOut
    employer_id: int
    employer_phone: str | None
    cancel_reason: str | None
    timeline: list[TransitionOut]


class AdminUserOut(BaseModel):
    id: int
    phone: str | None
    full_name: str | None
    status: str
    roles: list[str]
    created_at: datetime
    worker_status: str | None = None
    worker_reliability: int | None = None
    employer_reliability: int | None = None


class AuditOut(BaseModel):
    action: str
    actor_id: int | None
    before: dict | None
    after: dict | None
    created_at: datetime


async def _user_out(db, u: User) -> AdminUserOut:
    wp = await db.get(WorkerProfile, u.id)
    ep = await db.get(EmployerProfile, u.id)
    name = public_name(wp.first_name, wp.last_name) if wp and wp.first_name else u.full_name
    return AdminUserOut(
        id=u.id,
        phone=u.phone,
        full_name=name,
        status=u.status,
        roles=list(u.role_names),
        created_at=u.created_at,
        worker_status=wp.verification_status if wp else None,
        worker_reliability=wp.reliability if wp else None,
        employer_reliability=ep.reliability if ep else None,
    )


def _deliver(background: BackgroundTasks, svc, request: Request, redis, notifier) -> None:
    background.add_task(deliver_workday_outbox, svc, request.app.state.maker, redis, notifier, None)


# ---------------- operatsiya taxtasi (moderator + admin) ----------------
@router.get("/ops/board", response_model=BoardOut)
async def board(db: DbDep, _: Moderator):
    b = await AdminOpsService(db).board()
    return BoardOut(
        **{**vars(b), "call_queue": [vars(c) for c in b.call_queue], "problems": [vars(p) for p in b.problems]}
    )


@router.post("/ops/calls/{assignment_id}", status_code=204)
async def call_done(assignment_id: int, body: NoteIn, db: DbDep, user: Moderator):
    """Qo'ng'iroq qilindi — navbatdan chiqadi, izoh saqlanadi."""
    await AdminOpsService(db).mark_called(user, assignment_id, body.note)


# ---------------- nizolar (admin) ----------------
@router.post("/assignments/{assignment_id}/resolve", status_code=204)
async def resolve(
    assignment_id: int,
    body: ResolveIn,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
    admin: User = Depends(_admin),
):
    svc = AdminOpsService(db)
    await svc.resolve_dispute(admin, assignment_id, confirm=body.confirm, reason=body.reason, unfounded=body.unfounded)
    _deliver(background, svc, request, redis, notifier)


# ---------------- buyurtmalar (admin) ----------------
@router.get("/orders", response_model=list[OrderOut], dependencies=[Depends(_admin)])
async def orders(
    db: DbDep,
    status: str | None = None,
    q: str | None = Query(None, max_length=32),
    day: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Qidiruv: buyurtma raqami yoki ishchi/employer telefoni; kun bo'yicha (Toshkent vaqti)."""
    return [await _order_out(db, o) for o in await AdminOpsService(db).orders(status, q, day, limit, offset)]


@router.get("/orders/{order_id}", response_model=AdminOrderOut, dependencies=[Depends(_admin)])
async def order_detail(order_id: int, db: DbDep):
    order = await db.get(Order, order_id)
    if order is None:
        raise NotFound("Buyurtma topilmadi", code="ORDER_NOT_FOUND")
    employer = await db.get(User, order.employer_id)
    timeline = await AdminOpsService(db).order_timeline(order)
    return AdminOrderOut(
        order=await _order_out(db, order),
        employer_id=order.employer_id,
        employer_phone=employer.phone if employer else None,
        cancel_reason=order.cancel_reason,
        timeline=[TransitionOut.model_validate(t, from_attributes=True) for t in timeline],
    )


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def admin_cancel(
    order_id: int,
    body: ReasonIn,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
    admin: User = Depends(_admin),
):
    svc = AdminOpsService(db)
    order = await svc.admin_cancel(admin, order_id, body.reason)
    _deliver(background, svc, request, redis, notifier)
    return await _order_out(db, order)


@router.post("/orders/{order_id}/assign", response_model=OrderOut)
async def manual_assign(
    order_id: int,
    body: AssignIn,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    background: BackgroundTasks,
    admin: User = Depends(_admin),
):
    slot, matching = await AdminOpsService(db).manual_assign(admin, order_id, body.worker_id, redis, notifier)
    background.add_task(matching.flush_outbox)
    return await _order_out(db, await db.get(Order, order_id))


# ---------------- foydalanuvchilar (admin) ----------------
@router.get("/users", response_model=list[AdminUserOut], dependencies=[Depends(_admin)])
async def users(db: DbDep, q: str = Query(..., min_length=1, max_length=64)):
    return [await _user_out(db, u) for u in await AdminOpsService(db).users(q)]


@router.get("/users/{user_id}/history", response_model=list[AuditOut], dependencies=[Depends(_admin)])
async def user_history(user_id: int, db: DbDep):
    return [AuditOut.model_validate(a, from_attributes=True) for a in await AdminOpsService(db).user_history(user_id)]


@router.post("/users/{user_id}/block", response_model=AdminUserOut)
async def block(user_id: int, body: ReasonIn, db: DbDep, admin: User = Depends(_admin)):
    return await _user_out(db, await AdminOpsService(db).set_blocked(admin, user_id, True, body.reason))


@router.post("/users/{user_id}/unblock", response_model=AdminUserOut)
async def unblock(user_id: int, body: ReasonIn, db: DbDep, admin: User = Depends(_admin)):
    return await _user_out(db, await AdminOpsService(db).set_blocked(admin, user_id, False, body.reason))
