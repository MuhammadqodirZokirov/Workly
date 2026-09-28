from fastapi import APIRouter, BackgroundTasks, Query, Request

from workly.application.employer import BusinessModerationService
from workly.domain.worker import VerificationStatus

from ..deps import DbDep, Moderator, NotifierDep, client_ip
from ..schemas_employer import BusinessQueueItem, BusinessRejectIn, EmployerProfileOut

router = APIRouter(prefix="/admin/employers", tags=["admin"])


@router.get("", response_model=list[BusinessQueueItem])
async def queue(
    _: Moderator,
    db: DbDep,
    status: VerificationStatus = VerificationStatus.PENDING,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    svc = BusinessModerationService(db)
    return [
        BusinessQueueItem(
            user_id=p.user_id,
            company_name=p.company_name,
            stir=p.stir,
            responsible=p.user.full_name,
            phone=p.user.phone,
            submitted_at=p.submitted_at,
            same_stir_user_ids=await svc.same_stir_users(p),
        )
        for p in await svc.queue(status, limit, offset)
    ]


@router.post("/{user_id}/approve", response_model=EmployerProfileOut)
async def approve(
    user_id: int, moderator: Moderator, db: DbDep, notifier: NotifierDep, background: BackgroundTasks, request: Request
):
    profile = await BusinessModerationService(db).approve(moderator, user_id, client_ip(request))
    background.add_task(notifier.business_verification_result, user_id, True, None)
    return EmployerProfileOut.of(profile)


@router.post("/{user_id}/reject", response_model=EmployerProfileOut)
async def reject(
    user_id: int,
    body: BusinessRejectIn,
    moderator: Moderator,
    db: DbDep,
    notifier: NotifierDep,
    background: BackgroundTasks,
    request: Request,
):
    comment = (body.comment or "").strip() or None
    profile = await BusinessModerationService(db).reject(moderator, user_id, body.reason, comment, client_ip(request))
    background.add_task(notifier.business_verification_result, user_id, False, body.reason)
    return EmployerProfileOut.of(profile)
