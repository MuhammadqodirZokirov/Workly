from fastapi import APIRouter, Request, status

from workly.application.users import UserService

from ..deps import CurrentUser, DbDep
from ..schemas import ConsentIn, MeOut, MePatch, RoleIn

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=MeOut)
async def get_me(user: CurrentUser):
    return MeOut.of(user)


@router.patch("", response_model=MeOut)
async def patch_me(body: MePatch, user: CurrentUser, db: DbDep):
    await UserService(db).update_profile(user, full_name=body.full_name, lang=body.lang)
    return MeOut.of(user)


@router.post("/roles", response_model=MeOut)
async def add_role(body: RoleIn, user: CurrentUser, db: DbDep):
    await UserService(db).add_role(user, body.role)
    return MeOut.of(user)


@router.post("/consents", status_code=status.HTTP_204_NO_CONTENT)
async def accept_consents(body: ConsentIn, user: CurrentUser, db: DbDep, request: Request):
    await UserService(db).accept_consents(
        user,
        [(i.doc_type, i.version) for i in body.items],
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, db: DbDep):
    await UserService(db).delete_account(user)
