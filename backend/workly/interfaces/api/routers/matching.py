from fastapi import APIRouter, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from workly.application.matching import MatchingService
from workly.domain.employer import EmployerBadge, EmployerType
from workly.domain.orders import AssignmentStatus
from workly.infrastructure.db.models import EmployerProfile, Order, User

from ..deps import CurrentUser, DbDep, NotifierDep, RedisDep
from ..schemas_matching import (
    AvailabilityStatusIn,
    AvailabilityStatusOut,
    EmployerBrief,
    JobCard,
    OfferOut,
    WorkerAssignmentOut,
)
from ..schemas_worker import GeoPoint

router = APIRouter(tags=["matching"])


async def _employer_brief(db: AsyncSession, user_id: int) -> tuple[EmployerBrief, str | None]:
    user = await db.get(User, user_id)
    profile = await db.get(EmployerProfile, user_id)
    if profile and profile.type == EmployerType.BUSINESS and profile.company_name:
        name = profile.company_name
    else:
        parts = (user.full_name or "").split()
        name = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else (parts[0] if parts else None)
    verified = bool(profile and EmployerBadge.VERIFIED in (profile.badges or []))
    return EmployerBrief(name=name, verified=verified), user.phone


async def _card(db: AsyncSession, order: Order, distance: float | None) -> dict:
    brief, _ = await _employer_brief(db, order.employer_id)
    return dict(
        order_id=order.id,
        category_id=order.category_id,
        specialization_id=order.specialization_id,
        district_id=order.district_id,
        distance_km=distance,
        starts_at=order.starts_at,
        duration=order.duration,
        days=order.days,
        is_night=order.is_night,
        lunch=order.lunch,
        transport=order.transport,
        tools_by=order.tools_by,
        worker_net=order.price["worker_net"],
        open_slots=sum(1 for a in order.assignments if a.status == AssignmentStatus.OPEN),
        employer=brief,
        description=order.description,
    )


def _svc(db, redis, notifier) -> MatchingService:
    return MatchingService(db, redis, notifier)


@router.post("/worker/status", response_model=AvailabilityStatusOut)
async def set_status(body: AvailabilityStatusIn, user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep):
    """ "Hozir bo'shman" — shoshilinch buyurtmalar uchun; 8 soatdan keyin o'chadi."""
    p = await _svc(db, redis, notifier).set_available(user, body.available_now)
    return AvailabilityStatusOut(available_now=p.available_now_until is not None, until=p.available_now_until)


@router.get("/worker/offers", response_model=list[OfferOut])
async def my_offers(user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep):
    offers = await _svc(db, redis, notifier).active_offers(user)
    return [OfferOut(offer_id=o.id, expires_at=o.expires_at, **await _card(db, o.order, o.distance_km)) for o in offers]


@router.post("/offers/{offer_id}/accept", response_model=WorkerAssignmentOut)
async def accept(
    offer_id: int, user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep, background: BackgroundTasks
):
    offer = await _svc(db, redis, notifier).accept(user, offer_id)
    background.add_task(notifier.worker_assigned, offer.id)
    order = await db.get(Order, offer.order_id)
    return await _assignment_out(db, order, offer.assignment_id, offer.distance_km)


@router.post("/offers/{offer_id}/decline", status_code=204)
async def decline(offer_id: int, user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep):
    await _svc(db, redis, notifier).decline(user, offer_id)


@router.get("/jobs/open", response_model=list[JobCard])
async def open_jobs(user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep):
    """Ochiq ishlar lentasi: 1-to'lqindan keyin to'lmagan, kategoriya va hududga mos ishlar."""
    feed = await _svc(db, redis, notifier).open_feed(user)
    return [JobCard(**await _card(db, order, c.signals.distance_km)) for order, c in feed]


@router.post("/jobs/{order_id}/take", response_model=WorkerAssignmentOut)
async def take(
    order_id: int, user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep, background: BackgroundTasks
):
    offer = await _svc(db, redis, notifier).take_from_feed(user, order_id)
    background.add_task(notifier.worker_assigned, offer.id)
    order = await db.get(Order, offer.order_id)
    return await _assignment_out(db, order, offer.assignment_id, offer.distance_km)


@router.get("/worker/assignments", response_model=list[WorkerAssignmentOut])
async def my_assignments(user: CurrentUser, db: DbDep, redis: RedisDep, notifier: NotifierDep):
    return [
        await _assignment_out(db, await db.get(Order, a.order_id), a.id, None)
        for a in await _svc(db, redis, notifier).my_assignments(user)
    ]


async def _assignment_out(db: AsyncSession, order: Order, assignment_id: int, distance: float | None):
    """Tayinlangan ishchiga aniq manzil va employer telefoni ochiladi (TZ 4, OS-12)."""
    await db.refresh(order, attribute_names=["assignments"])
    a = next(x for x in order.assignments if x.id == assignment_id)
    _, phone = await _employer_brief(db, order.employer_id)
    return WorkerAssignmentOut(
        assignment_id=a.id,
        status=a.status,
        address_text=order.address_text,
        landmark=order.landmark,
        point=GeoPoint(lat=order.lat, lon=order.lon),
        employer_phone=phone,
        arrived_at=a.arrived_at,
        finished_at=a.finished_at,
        confirmed_at=a.confirmed_at,
        cash_received=a.cash_received,
        **await _card(db, order, distance),
    )
