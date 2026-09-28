from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Response
from pydantic import BaseModel

from workly.application.employer import _UNSET, EmployerInput, EmployerService
from workly.application.relations import RelationsService

from ..deps import CurrentUser, DbDep, NotifierDep
from ..schemas_employer import EmployerProfileIn, EmployerProfileOut

router = APIRouter(prefix="/employer", tags=["employer"])


@router.get("/profile", response_model=EmployerProfileOut)
async def get_profile(user: CurrentUser, db: DbDep):
    return EmployerProfileOut.of(await EmployerService(db).get_profile(user, create=True))


@router.put("/profile", response_model=EmployerProfileOut)
async def put_profile(body: EmployerProfileIn, user: CurrentUser, db: DbDep):
    sent = body.model_fields_set
    data = EmployerInput(
        type=body.type,
        company_name=body.company_name,
        stir=body.stir,
        activity=body.activity,
        address_text=body.address_text,
        district_id=body.district_id if "district_id" in sent else _UNSET,
        point=((body.point.lat, body.point.lon) if body.point else None) if "point" in sent else _UNSET,
    )
    return EmployerProfileOut.of(await EmployerService(db).update_profile(user, data))


@router.post("/verification", response_model=EmployerProfileOut)
async def submit_business(user: CurrentUser, db: DbDep, notifier: NotifierDep, background: BackgroundTasks):
    out = EmployerProfileOut.of(await EmployerService(db).submit_business(user))
    background.add_task(notifier.admin_signal, "business", user.id)
    return out


# ---------- sevimli va bloklangan ishchilar (TZ 5) ----------
class KnownWorkerOut(BaseModel):
    worker_id: int
    name: str | None
    jobs: int
    last_job_at: datetime
    favorite: bool
    blocked: bool


@router.get("/workers", response_model=list[KnownWorkerOut])
async def known_workers(user: CurrentUser, db: DbDep):
    """Men bilan ishlagan ishchilar — sevimli qilish yoki bloklash uchun."""
    return [KnownWorkerOut(**vars(w)) for w in await RelationsService(db).known_workers(user)]


@router.put("/favorites/{worker_id}", status_code=204)
async def add_favorite(worker_id: int, user: CurrentUser, db: DbDep):
    await RelationsService(db).set_favorite(user, worker_id, True)
    return Response(status_code=204)


@router.delete("/favorites/{worker_id}", status_code=204)
async def remove_favorite(worker_id: int, user: CurrentUser, db: DbDep):
    await RelationsService(db).set_favorite(user, worker_id, False)
    return Response(status_code=204)


@router.put("/blocks/{worker_id}", status_code=204)
async def block_worker(worker_id: int, user: CurrentUser, db: DbDep):
    await RelationsService(db).set_block(user, worker_id, True)
    return Response(status_code=204)


@router.delete("/blocks/{worker_id}", status_code=204)
async def unblock_worker(worker_id: int, user: CurrentUser, db: DbDep):
    await RelationsService(db).set_block(user, worker_id, False)
    return Response(status_code=204)
