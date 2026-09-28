from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from workly.application.cancellation import CancellationService
from workly.application.workday import WorkdayService
from workly.domain.errors import ValidationFailed
from workly.infrastructure.db.models import Assignment, Review
from workly.workers.scheduler import deliver_workday_outbox

from ..deps import CurrentUser, DbDep, NotifierDep, RedisDep, SettingsDep, StorageDep
from ..schemas_orders import CancelTermsOut

router = APIRouter(prefix="/assignments", tags=["workday"])


class AssignmentStateOut(BaseModel):
    id: int
    order_id: int
    status: str
    arrived_at: datetime | None
    arrival_confirmed_at: datetime | None
    finished_at: datetime | None
    confirmed_at: datetime | None
    auto_confirmed: bool
    cash_received: int | None
    problem: str | None

    @classmethod
    def of(cls, a: Assignment) -> "AssignmentStateOut":
        return cls(
            id=a.id,
            order_id=a.order_id,
            status=a.status,
            arrived_at=a.arrived_at,
            arrival_confirmed_at=a.arrival_confirmed_at,
            finished_at=a.finished_at,
            confirmed_at=a.confirmed_at,
            auto_confirmed=a.auto_confirmed,
            cash_received=a.cash_received,
            problem=a.problem,
        )


class ArrivalIn(BaseModel):
    same_person: bool


class ConfirmIn(BaseModel):
    ok: bool
    reason: str | None = Field(default=None, max_length=300)


class CashIn(BaseModel):
    amount: int = Field(ge=0, le=100_000_000)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=5)
    comment: str | None = Field(default=None, max_length=300)


class ReviewOut(BaseModel):
    rating: float
    tags: list[str]
    comment: str | None
    is_auto: bool
    mine: bool


class ReviewsOut(BaseModel):
    reviewed_by_me: bool
    visible: list[ReviewOut]  # yashirin baho ikkalasi baholagach yoki 48 soatdan keyin ochiladi


def _after_commit(background: BackgroundTasks, svc: WorkdayService, request: Request, redis, notifier) -> None:
    background.add_task(
        deliver_workday_outbox, svc, request.app.state.maker, redis, notifier, request.app.state.storage
    )


@router.post("/{assignment_id}/checkin", response_model=AssignmentStateOut)
async def checkin(
    assignment_id: int,
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    settings: SettingsDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
    lat: float = Form(..., ge=-90, le=90),
    lon: float = Form(..., ge=-180, le=180),
    accuracy: float = Form(..., ge=0, le=10_000),
    selfie: UploadFile = File(...),
):
    """GPS (≤ 200 m, aniqlik ≤ 100 m) + ilova ichida jonli selfie (TZ 10)."""
    limit = settings.max_upload_mb * 1024 * 1024
    data = await selfie.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailed("Fayl hajmi juda katta", code="FILE_TOO_LARGE")
    svc = WorkdayService(db, storage)
    a = await svc.checkin(user, assignment_id, lat, lon, accuracy, data)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


@router.post("/{assignment_id}/confirm-arrival", response_model=AssignmentStateOut)
async def confirm_arrival(
    assignment_id: int,
    body: ArrivalIn,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
):
    svc = WorkdayService(db)
    a = await svc.confirm_arrival(user, assignment_id, body.same_person)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


@router.post("/{assignment_id}/finish", response_model=AssignmentStateOut)
async def finish(
    assignment_id: int,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
):
    svc = WorkdayService(db)
    a = await svc.finish(user, assignment_id)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


@router.post("/{assignment_id}/confirm", response_model=AssignmentStateOut)
async def confirm(
    assignment_id: int,
    body: ConfirmIn,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
):
    """Employer: "Ha, bajarildi" yoki "Muammo bor" (kamida 20 belgi)."""
    svc = WorkdayService(db)
    a = await svc.confirm_work(user, assignment_id, body.ok, body.reason)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


@router.post("/{assignment_id}/cash-received", response_model=AssignmentStateOut)
async def cash_received(
    assignment_id: int,
    body: CashIn,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
):
    svc = WorkdayService(db)
    a = await svc.cash_received(user, assignment_id, body.amount)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


@router.post("/{assignment_id}/replace", response_model=AssignmentStateOut)
async def replace(
    assignment_id: int,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
):
    """Employer: ishchi 30 daqiqadan ko'p kechiksa — almashtirish."""
    svc = WorkdayService(db)
    a = await svc.replace(user, assignment_id)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


class WorkerCancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


@router.get("/{assignment_id}/cancel-preview", response_model=CancelTermsOut)
async def cancel_preview(assignment_id: int, user: CurrentUser, db: DbDep):
    return CancelTermsOut.of(await CancellationService(db).worker_preview(user, assignment_id))


@router.post("/{assignment_id}/cancel", response_model=AssignmentStateOut)
async def worker_cancel(
    assignment_id: int,
    body: WorkerCancelIn,
    user: CurrentUser,
    db: DbDep,
    redis: RedisDep,
    notifier: NotifierDep,
    request: Request,
    background: BackgroundTasks,
):
    """Ishchi ish boshlanishidan oldin bekor qiladi; o'rniga yangi ishchi izlanadi (TZ 11)."""
    svc = CancellationService(db)
    a, _ = await svc.worker_cancel(user, assignment_id, body.reason)
    _after_commit(background, svc, request, redis, notifier)
    return AssignmentStateOut.of(a)


@router.post("/{assignment_id}/review", response_model=ReviewsOut, status_code=201)
async def review(assignment_id: int, body: ReviewIn, user: CurrentUser, db: DbDep):
    await WorkdayService(db).review(user, assignment_id, body.rating, body.tags, body.comment)
    return await _reviews(db, user.id, assignment_id)


@router.get("/{assignment_id}/reviews", response_model=ReviewsOut)
async def reviews(assignment_id: int, user: CurrentUser, db: DbDep):
    a = await WorkdayService(db)._assignment(assignment_id)
    if user.id not in (a.worker_id, a.order.employer_id):
        from workly.domain.errors import NotFound

        raise NotFound("Tayinlov topilmadi", code="ASSIGNMENT_NOT_FOUND")
    return await _reviews(db, user.id, assignment_id)


async def _reviews(db, user_id: int, assignment_id: int) -> ReviewsOut:
    rows = list(await db.scalars(select(Review).where(Review.assignment_id == assignment_id)))
    return ReviewsOut(
        reviewed_by_me=any(r.author_id == user_id for r in rows),
        visible=[
            ReviewOut(
                rating=r.rating, tags=r.tags or [], comment=r.comment, is_auto=r.is_auto, mine=r.author_id == user_id
            )
            for r in rows
            if r.visible_at is not None or r.author_id == user_id
        ],
    )
