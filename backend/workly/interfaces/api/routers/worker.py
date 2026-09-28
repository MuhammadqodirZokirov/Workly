from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

from workly.application.worker import ProfileInput, SkillInput, SlotInput, WorkerService
from workly.domain.errors import ValidationFailed
from workly.domain.worker import FileKind

from ..deps import CipherDep, CurrentUser, DbDep, SettingsDep, StorageDep
from ..schemas_worker import AvailabilityIn, FileOut, SubmitIn, WorkerProfileIn, WorkerProfileOut

router = APIRouter(prefix="/worker", tags=["worker"])


async def _out(svc: WorkerService, profile) -> WorkerProfileOut:
    return WorkerProfileOut.of(profile, await svc.list_files(profile.user_id))


@router.get("/profile", response_model=WorkerProfileOut)
async def get_profile(user: CurrentUser, db: DbDep):
    svc = WorkerService(db)
    return await _out(svc, await svc.get_profile(user, create=True))


@router.put("/profile", response_model=WorkerProfileOut)
async def put_profile(body: WorkerProfileIn, user: CurrentUser, db: DbDep):
    sent = body.model_fields_set
    data = ProfileInput(
        last_name=body.last_name,
        first_name=body.first_name,
        middle_name=body.middle_name,
        birth_date=body.birth_date,
        gender=body.gender,
        district_ids=body.district_ids,
        home_point=(body.home_point.lat, body.home_point.lon) if body.home_point else None,
        clear_home_point="home_point" in sent and body.home_point is None,
        skills=[SkillInput(s.category_id, s.experience, s.specialization_ids) for s in body.skills]
        if body.skills is not None
        else None,
        emergency_name=body.emergency_contact.name if body.emergency_contact else None,
        emergency_phone=body.emergency_contact.phone if body.emergency_contact else None,
        clear_emergency="emergency_contact" in sent and body.emergency_contact is None,
    )
    svc = WorkerService(db)
    return await _out(svc, await svc.update_profile(user, data))


@router.put("/availability", response_model=WorkerProfileOut)
async def put_availability(body: AvailabilityIn, user: CurrentUser, db: DbDep):
    svc = WorkerService(db)
    profile = await svc.set_availability(user, [SlotInput(s.weekday, s.start, s.end) for s in body.slots])
    return await _out(svc, profile)


@router.post("/files", response_model=FileOut, status_code=201)
async def upload_file(
    user: CurrentUser,
    db: DbDep,
    storage: StorageDep,
    settings: SettingsDep,
    background: BackgroundTasks,
    kind: FileKind = Form(...),
    file: UploadFile = File(...),
):
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ValidationFailed("Fayl hajmi juda katta", code="FILE_TOO_LARGE", details={"max_bytes": limit})
    svc = WorkerService(db, storage=storage, max_upload_bytes=limit)
    new, old_keys = await svc.upload_file(user, kind, data)
    # Eski nusxalar javobdan keyin (commit bo'lgach) o'chiriladi
    for key in old_keys:
        background.add_task(storage.delete, key)
    return FileOut(id=new.id, kind=new.kind, content_type=new.content_type, size=new.size, created_at=new.created_at)


@router.post("/verification", response_model=WorkerProfileOut)
async def submit_verification(body: SubmitIn, user: CurrentUser, db: DbDep, cipher: CipherDep):
    svc = WorkerService(db, cipher=cipher)
    return await _out(svc, await svc.submit_verification(user, body.doc_type, body.doc_number))
