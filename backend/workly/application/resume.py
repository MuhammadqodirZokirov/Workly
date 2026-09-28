"""Ishchining ommaviy profili (rezyume) — ish beruvchi ko'radigan qism (TZ 4-bo'lim).

Yashirin: telefon (tayinlovgacha), hujjat, selfie, aniq manzil va uy nuqtasi.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import NotFound
from workly.domain.names import public_name
from workly.domain.users import UserStatus
from workly.domain.worker import NEW_BADGE_MAX_REVIEWS, FileKind, VerificationStatus
from workly.infrastructure.db.models import WorkerFile, WorkerProfile

from .ratings import WorkerStats, worker_stats


@dataclass
class Resume:
    worker_id: int
    display_name: str | None
    avatar_key: str | None
    skills: list[tuple[int, str, list[int]]]  # (category_id, experience, specialization_ids)
    district_ids: list[int]
    badges: list[str]
    stats: WorkerStats

    @property
    def is_new(self) -> bool:
        return self.stats.reviews_count < NEW_BADGE_MAX_REVIEWS


class ResumeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, worker_id: int) -> Resume:
        profile = await self.db.get(WorkerProfile, worker_id)
        # Faqat tasdiqlangan va faol ishchi ko'rinadi
        if (
            profile is None
            or profile.verification_status != VerificationStatus.VERIFIED
            or profile.user.status != UserStatus.ACTIVE
        ):
            raise NotFound("Ishchi topilmadi", code="WORKER_NOT_FOUND")
        avatar = await self.db.scalar(
            select(WorkerFile.storage_key).where(
                WorkerFile.user_id == worker_id, WorkerFile.kind == FileKind.AVATAR, WorkerFile.deleted_at.is_(None)
            )
        )
        specs: dict[int, list[int]] = {}
        for sp in profile.specializations:
            specs.setdefault(sp.category_id, []).append(sp.specialization_id)
        return Resume(
            worker_id=worker_id,
            display_name=public_name(profile.first_name, profile.last_name),
            avatar_key=avatar,
            skills=[(s.category_id, s.experience, specs.get(s.category_id, [])) for s in profile.skills],
            district_ids=[d.district_id for d in profile.districts],
            badges=list(profile.badges or []),
            stats=await worker_stats(self.db, worker_id),
        )
