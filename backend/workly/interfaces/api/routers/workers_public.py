from fastapi import APIRouter, Depends, Request

from workly.application.resume import ResumeService
from workly.domain.users import Role
from workly.infrastructure.storage import sign_file_url

from ..deps import DbDep, SettingsDep, require_roles
from ..schemas_worker import ResumeOut, ResumeSkill, ResumeStats

router = APIRouter(prefix="/workers", tags=["workers"])

# Rezyumeni ish beruvchi va moderatorlar ko'radi
_viewer = require_roles(Role.EMPLOYER, Role.MODERATOR, Role.ADMIN)


@router.get("/{worker_id}", response_model=ResumeOut, dependencies=[Depends(_viewer)])
async def resume(worker_id: int, db: DbDep, settings: SettingsDep, request: Request):
    r = await ResumeService(db).get(worker_id)
    avatar_url = None
    if r.avatar_key:
        exp, sig = sign_file_url(r.avatar_key, settings.jwt_secret.get_secret_value(), settings.signed_url_ttl)
        avatar_url = str(request.url_for("get_file", key=r.avatar_key).include_query_params(exp=exp, sig=sig))
    s = r.stats
    return ResumeOut(
        worker_id=r.worker_id,
        display_name=r.display_name,
        avatar_url=avatar_url,
        is_new=r.is_new,
        badges=r.badges,
        district_ids=r.district_ids,
        skills=[ResumeSkill(category_id=c, experience=e, specialization_ids=sp) for c, e, sp in r.skills],
        stats=ResumeStats(
            rating=s.rating,
            reviews_count=s.reviews_count,
            reliability=s.reliability,
            completed_jobs=s.completed_jobs,
            no_shows_90d=s.no_shows_90d,
            avg_response_minutes=s.avg_response_minutes,
        ),
        recent_reviews=s.recent_reviews,
    )
