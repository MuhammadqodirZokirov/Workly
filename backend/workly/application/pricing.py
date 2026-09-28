from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import ValidationFailed
from workly.domain.pricing import MAX_FACTOR, MIN_FACTOR, PriceConfig, PriceUnit, bound
from workly.infrastructure.db.models import Category, PriceConfigRow, Specialization, User

from .audit import audit


class PriceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve(self, category_id: int, specialization_id: int) -> tuple[PriceConfigRow, PriceConfig]:
        """Mutaxassislik narxi bo'lsa — u, aks holda kategoriya narxi. Eng so'nggi faol versiya."""
        now = datetime.now(UTC)
        for spec in (specialization_id, None):
            q = (
                select(PriceConfigRow)
                .where(PriceConfigRow.category_id == category_id, PriceConfigRow.active_from <= now)
                .order_by(PriceConfigRow.active_from.desc(), PriceConfigRow.id.desc())
                .limit(1)
            )
            q = (
                q.where(PriceConfigRow.specialization_id == spec)
                if spec
                else q.where(PriceConfigRow.specialization_id.is_(None))
            )
            row = await self.db.scalar(q)
            if row is not None:
                return row, PriceConfig(
                    PriceUnit(row.unit), row.base, row.min_price, row.max_price, row.min_order_amount
                )
        raise ValidationFailed("Bu ish turi uchun narx hali belgilanmagan", code="PRICE_NOT_CONFIGURED")

    async def current(self) -> list[PriceConfigRow]:
        rows = (
            await self.db.scalars(
                select(PriceConfigRow).order_by(
                    PriceConfigRow.category_id,
                    PriceConfigRow.specialization_id,
                    PriceConfigRow.active_from.desc(),
                    PriceConfigRow.id.desc(),
                )
            )
        ).all()
        seen, out = set(), []
        for r in rows:
            key = (r.category_id, r.specialization_id)
            if key not in seen:
                seen.add(key)
                out.append(r)
        return out

    async def set_price(
        self,
        admin: User,
        *,
        category_id: int,
        specialization_id: int | None,
        unit: PriceUnit,
        base: int,
        min_price: int | None,
        max_price: int | None,
        min_order_amount: int,
        ip: str | None,
    ) -> PriceConfigRow:
        if await self.db.get(Category, category_id) is None:
            raise ValidationFailed("Kategoriya topilmadi", code="INVALID_CATEGORY")
        if specialization_id is not None:
            spec = await self.db.get(Specialization, specialization_id)
            if spec is None or spec.category_id != category_id:
                raise ValidationFailed("Mutaxassislik bu kategoriyaga tegishli emas", code="INVALID_SPECIALIZATION")
        min_price = min_price if min_price is not None else bound(base, MIN_FACTOR)
        max_price = max_price if max_price is not None else bound(base, MAX_FACTOR)
        if not (0 < min_price <= base <= max_price):
            raise ValidationFailed("min ≤ bazaviy ≤ max bo'lishi kerak", code="INVALID_PRICE")
        row = PriceConfigRow(
            category_id=category_id,
            specialization_id=specialization_id,
            unit=unit,
            base=base,
            min_price=min_price,
            max_price=max_price,
            min_order_amount=min_order_amount,
            created_by=admin.id,
        )
        self.db.add(row)
        await self.db.flush()
        audit(
            self.db,
            admin.id,
            "price.set",
            "price_config",
            row.id,
            ip=ip,
            after={
                "category_id": category_id,
                "specialization_id": specialization_id,
                "unit": unit,
                "base": base,
                "min": min_price,
                "max": max_price,
                "min_order": min_order_amount,
            },
        )
        return row
