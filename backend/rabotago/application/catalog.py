from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rabotago.infrastructure.db.models import Category, District, Region


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def categories(self) -> list[Category]:
        rows = await self.db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order))
        return list(rows)

    async def regions(self) -> list[Region]:
        rows = await self.db.scalars(select(Region).where(Region.is_active.is_(True)).order_by(Region.sort_order))
        return list(rows)

    async def districts(self, region_id: int | None = None) -> list[District]:
        q = (
            select(District)
            .join(Region)
            .where(District.is_active.is_(True), Region.is_active.is_(True))
            .order_by(District.region_id, District.sort_order)
        )
        if region_id is not None:
            q = q.where(District.region_id == region_id)
        return list(await self.db.scalars(q))
