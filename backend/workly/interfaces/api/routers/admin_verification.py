from fastapi import APIRouter, BackgroundTasks, Query, Request

from workly.application.verification import VerificationService
from workly.application.worker import WorkerService, today_tashkent
from workly.domain.worker import VerificationStatus, age_on
from workly.infrastructure.storage import sign_file_url

from ..deps import CipherDep, DbDep, Moderator, NotifierDep, SettingsDep, client_ip
from ..schemas_worker import ApproveIn, CaseOut, FileLink, QueueItem, RejectIn, WorkerProfileOut

router = APIRouter(prefix="/admin/verifications", tags=["admin"])


@router.get("", response_model=list[QueueItem])
async def queue(
    _: Moderator,
    db: DbDep,
    cipher: CipherDep,
    status: VerificationStatus = VerificationStatus.PENDING,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    today = today_tashkent()
    return [
        QueueItem(
            user_id=p.user_id,
            full_name=p.user.full_name,
            age=age_on(p.birth_date, today) if p.birth_date else None,
            submitted_at=p.submitted_at,
            duplicate_of_user_id=p.duplicate_of_user_id,
        )
        for p in await VerificationService(db, cipher).queue(status, limit, offset)
    ]


@router.get("/{user_id}", response_model=CaseOut)
async def open_case(
    user_id: int, moderator: Moderator, db: DbDep, cipher: CipherDep, settings: SettingsDep, request: Request
):
    profile, doc_number, files = await VerificationService(db, cipher).open_case(moderator, user_id, client_ip(request))
    secret = settings.jwt_secret.get_secret_value()
    links = []
    for f in files:
        exp, sig = sign_file_url(f.storage_key, secret, settings.signed_url_ttl)
        # Nisbiy yo'l — proksi/Nginx orqasida host noto'g'ri bo'lib qolmasin
        url = f"{request.app.url_path_for('get_file', key=f.storage_key)}?exp={exp}&sig={sig}"
        links.append(
            FileLink(
                id=f.id,
                kind=f.kind,
                content_type=f.content_type,
                size=f.size,
                created_at=f.created_at,
                url=url,
                expires_at=exp,
            )
        )
    return CaseOut(
        profile=WorkerProfileOut.of(profile, files),
        phone=profile.user.phone,
        doc_number=doc_number,
        duplicate_of_user_id=profile.duplicate_of_user_id,
        files=links,
    )


@router.post("/{user_id}/approve", response_model=WorkerProfileOut)
async def approve(
    user_id: int,
    body: ApproveIn,
    moderator: Moderator,
    db: DbDep,
    cipher: CipherDep,
    notifier: NotifierDep,
    background: BackgroundTasks,
    request: Request,
):
    profile = await VerificationService(db, cipher).approve(moderator, user_id, body.badges, client_ip(request))
    background.add_task(notifier.verification_result, user_id, True, None)
    return WorkerProfileOut.of(profile, await WorkerService(db).list_files(user_id))


@router.post("/{user_id}/reject", response_model=WorkerProfileOut)
async def reject(
    user_id: int,
    body: RejectIn,
    moderator: Moderator,
    db: DbDep,
    cipher: CipherDep,
    notifier: NotifierDep,
    background: BackgroundTasks,
    request: Request,
):
    profile = await VerificationService(db, cipher).reject(
        moderator, user_id, body.reason, body.comment, client_ip(request)
    )
    background.add_task(notifier.verification_result, user_id, False, body.reason)
    return WorkerProfileOut.of(profile, await WorkerService(db).list_files(user_id))
