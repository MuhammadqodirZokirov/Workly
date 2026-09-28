"""Katalog sozlamalari: kategoriya, ish turi, hudud; avtomatik baholar (TZ 16, admin bot).

Web panel va admin bot bir xil servisni chaqiradi; har o'zgarish audit jurnaliga yoziladi.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.errors import Conflict, NotFound, ValidationFailed
from workly.domain.translit import latin_to_cyrillic
from workly.infrastructure.db.models import Category, District, Region, Review, Specialization, User

from .audit import audit

KINDS = {"category": Category, "specialization": Specialization, "district": District, "region": Region}
NAME_RE = re.compile(r"^[\w'ʻ’ .,()\-/]{2,60}$")


def slugify(latin: str) -> str:
    """Lotin nomdan kod: "Plitka ustasi" → "plitka_ustasi"."""
    s = latin.lower().replace("'", "").replace("ʻ", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:32] or "item"


def check_name(value: str, field: str) -> str:
    value = " ".join((value or "").split())
    if not NAME_RE.match(value):
        raise ValidationFailed(f"{field}: 2–60 belgi, harf va raqamlar", code="INVALID_NAME")
    return value


class AdminCatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def categories(self) -> list[Category]:
        """Hammasi — o'chirilganlari ham (admin ko'radi)."""
        return list(await self.db.scalars(select(Category).order_by(Category.sort_order, Category.id)))

    async def category(self, category_id: int) -> Category:
        c = await self.db.get(Category, category_id)
        if c is None:
            raise NotFound("Kategoriya topilmadi", code="CATEGORY_NOT_FOUND")
        return c

    async def districts(self) -> list[District]:
        return list(await self.db.scalars(select(District).order_by(District.region_id, District.sort_order)))

    async def toggle(self, admin: User, kind: str, item_id: int) -> bool:
        model = KINDS.get(kind)
        item = await self.db.get(model, item_id) if model else None
        if item is None:
            raise NotFound("Topilmadi", code="NOT_FOUND")
        item.is_active = not item.is_active
        audit(self.db, admin.id, f"catalog.{kind}.toggle", kind, item.id, after={"is_active": item.is_active})
        await self.db.flush()
        return item.is_active

    def preview(self, latin: str, ru: str) -> dict[str, str]:
        """Kirill lotindan avtomatik — saqlashdan oldin ko'rsatiladi (TZ 16)."""
        latin, ru = check_name(latin, "Lotin"), check_name(ru, "Rus")
        return {"uz_latn": latin, "uz_cyrl": latin_to_cyrillic(latin), "ru": ru}

    async def create_category(self, admin: User, latin: str, ru: str) -> Category:
        names = self.preview(latin, ru)
        code = slugify(names["uz_latn"])
        if await self.db.scalar(select(Category.id).where(Category.code == code)):
            raise Conflict("Bunday kategoriya bor", code="DUPLICATE")
        sort = (await self.db.scalar(select(func.max(Category.sort_order)))) or 0
        c = Category(
            code=code,
            name_uz_latn=names["uz_latn"],
            name_uz_cyrl=names["uz_cyrl"],
            name_ru=names["ru"],
            sort_order=sort + 10,
        )
        self.db.add(c)
        await self.db.flush()
        audit(self.db, admin.id, "catalog.category.create", "category", c.id, after=names)
        return c

    async def create_specialization(self, admin: User, category_id: int, latin: str, ru: str) -> Specialization:
        category = await self.category(category_id)
        names = self.preview(latin, ru)
        code = slugify(names["uz_latn"])
        exists = await self.db.scalar(
            select(Specialization.id).where(Specialization.category_id == category.id, Specialization.code == code)
        )
        if exists:
            raise Conflict("Bu kategoriyada shunday ish turi bor", code="DUPLICATE")
        sort = (
            await self.db.scalar(
                select(func.max(Specialization.sort_order)).where(Specialization.category_id == category.id)
            )
        ) or 0
        s = Specialization(
            category_id=category.id,
            code=code,
            name_uz_latn=names["uz_latn"],
            name_uz_cyrl=names["uz_cyrl"],
            name_ru=names["ru"],
            sort_order=sort + 10,
        )
        self.db.add(s)
        await self.db.flush()
        audit(self.db, admin.id, "catalog.specialization.create", "specialization", s.id, after=names)
        return s

    # ---------- avtomatik baholar ----------
    async def auto_reviews(self, limit: int = 10) -> list[Review]:
        rows = await self.db.scalars(
            select(Review)
            .where(Review.is_auto.is_(True), Review.hidden_by_admin.is_(False))
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        return list(rows)

    async def hide_review(self, admin: User, review_id: int) -> Review:
        review = await self.db.get(Review, review_id)
        if review is None:
            raise NotFound("Baho topilmadi", code="REVIEW_NOT_FOUND")
        review.hidden_by_admin = True
        audit(self.db, admin.id, "review.hide", "review", review.id, after={"is_auto": review.is_auto})
        await self.db.flush()
        return review
