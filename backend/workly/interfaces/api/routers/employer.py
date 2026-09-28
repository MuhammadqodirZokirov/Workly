from fastapi import APIRouter

from workly.application.employer import _UNSET, EmployerInput, EmployerService

from ..deps import CurrentUser, DbDep
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
async def submit_business(user: CurrentUser, db: DbDep):
    return EmployerProfileOut.of(await EmployerService(db).submit_business(user))
