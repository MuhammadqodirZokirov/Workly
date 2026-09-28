"""Employer ↔ ishchi munosabatlari: sevimlilar va bloklar (TZ 5, 7).

Faqat shu employer bilan ishlagan (tayinlangan) ishchini sevimli yoki bloklangan qilish mumkin —
begona ishchilar ID bo'yicha taxmin qilinmasin.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import NotFound
from workly.domain.names import public_name
from workly.infrastructure.db.models import Assignment, EmployerBlock, EmployerFavorite, Order, User, WorkerProfile

from .audit import audit


@dataclass
class KnownWorker:
    worker_id: int
    name: str | None
    jobs: int
    last_job_at: datetime
    favorite: bool
    blocked: bool


async def favorite_ids(db: AsyncSession, employer_id: int) -> set[int]:
    return set(
        (await db.scalars(select(EmployerFavorite.worker_id).where(EmployerFavorite.employer_id == employer_id))).all()
    )


async def blocked_ids(db: AsyncSession, employer_id: int) -> set[int]:
    return set(
        (await db.scalars(select(EmployerBlock.worker_id).where(EmployerBlock.employer_id == employer_id))).all()
    )


class RelationsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_known(self, employer: User, worker_id: int) -> None:
        known = await self.db.scalar(
            select(Assignment.id)
            .join(Order, Order.id == Assignment.order_id)
            .where(Order.employer_id == employer.id, Assignment.worker_id == worker_id)
            .limit(1)
        )
        if known is None:
            raise NotFound("Ishchi topilmadi", code="WORKER_NOT_FOUND")

    async def known_workers(self, employer: User) -> list[KnownWorker]:
        rows = (
            await self.db.execute(
                select(Assignment.worker_id, func.count(Assignment.id), func.max(Order.starts_at))
                .join(Order, Order.id == Assignment.order_id)
                .where(Order.employer_id == employer.id, Assignment.worker_id.is_not(None))
                .group_by(Assignment.worker_id)
                .order_by(func.max(Order.starts_at).desc())
            )
        ).all()
        favs, blocks = await favorite_ids(self.db, employer.id), await blocked_ids(self.db, employer.id)
        out = []
        for wid, jobs, last in rows:
            profile = await self.db.get(WorkerProfile, wid)
            out.append(
                KnownWorker(
                    worker_id=wid,
                    name=public_name(profile.first_name, profile.last_name) if profile else None,
                    jobs=jobs,
                    last_job_at=last,
                    favorite=wid in favs,
                    blocked=wid in blocks,
                )
            )
        return out

    async def set_favorite(self, employer: User, worker_id: int, on: bool) -> None:
        await self._ensure_known(employer, worker_id)
        exists = await self.db.get(EmployerFavorite, (employer.id, worker_id))
        if on and not exists:
            # Sevimli va bloklangan bir vaqtda bo'lmaydi
            await self.db.execute(
                delete(EmployerBlock).where(
                    EmployerBlock.employer_id == employer.id, EmployerBlock.worker_id == worker_id
                )
            )
            self.db.add(EmployerFavorite(employer_id=employer.id, worker_id=worker_id))
        elif not on and exists:
            await self.db.delete(exists)
        await self.db.flush()

    async def set_block(self, employer: User, worker_id: int, on: bool) -> None:
        await self._ensure_known(employer, worker_id)
        exists = await self.db.get(EmployerBlock, (employer.id, worker_id))
        if on and not exists:
            await self.db.execute(
                delete(EmployerFavorite).where(
                    EmployerFavorite.employer_id == employer.id, EmployerFavorite.worker_id == worker_id
                )
            )
            self.db.add(EmployerBlock(employer_id=employer.id, worker_id=worker_id))
            audit(self.db, employer.id, "employer.block_worker", "user", worker_id)
        elif not on and exists:
            await self.db.delete(exists)
            audit(self.db, employer.id, "employer.unblock_worker", "user", worker_id)
        await self.db.flush()
