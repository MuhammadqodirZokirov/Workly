"""Boshlang'ich katalog: hududlar, tumanlar, kategoriyalar (TZ 4-bo'lim).

Idempotent: mavjud yozuvlarga tegmaydi (admin o'zgartirgan bo'lishi mumkin), faqat yo'qlarini qo'shadi.
    python -m workly.infrastructure.seed
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workly.domain.translit import latin_to_cyrillic

from .config import get_settings
from .db.models import Category, District, Region, Specialization
from .db.session import make_engine, make_sessionmaker

# (code, lotin, rus, faol)
REGIONS = [
    ("tashkent_city", "Toshkent shahri", "город Ташкент", True),
    ("tashkent", "Toshkent viloyati", "Ташкентская область", False),
    ("andijan", "Andijon viloyati", "Андижанская область", False),
    ("bukhara", "Buxoro viloyati", "Бухарская область", False),
    ("fergana", "Farg'ona viloyati", "Ферганская область", False),
    ("jizzakh", "Jizzax viloyati", "Джизакская область", False),
    ("khorezm", "Xorazm viloyati", "Хорезмская область", False),
    ("namangan", "Namangan viloyati", "Наманганская область", False),
    ("navoi", "Navoiy viloyati", "Навоийская область", False),
    ("kashkadarya", "Qashqadaryo viloyati", "Кашкадарьинская область", False),
    ("karakalpakstan", "Qoraqalpog'iston Respublikasi", "Республика Каракалпакстан", False),
    ("samarkand", "Samarqand viloyati", "Самаркандская область", False),
    ("syrdarya", "Sirdaryo viloyati", "Сырдарьинская область", False),
    ("surkhandarya", "Surxondaryo viloyati", "Сурхандарьинская область", False),
]

TASHKENT_DISTRICTS = [
    ("bektemir", "Bektemir", "Бектемирский"),
    ("chilonzor", "Chilonzor", "Чиланзарский"),
    ("mirobod", "Mirobod", "Мирабадский"),
    ("mirzo_ulugbek", "Mirzo Ulug'bek", "Мирзо-Улугбекский"),
    ("olmazor", "Olmazor", "Алмазарский"),
    ("sergeli", "Sergeli", "Сергелийский"),
    ("shayxontohur", "Shayxontohur", "Шайхантахурский"),
    ("uchtepa", "Uchtepa", "Учтепинский"),
    ("yakkasaroy", "Yakkasaroy", "Яккасарайский"),
    ("yangihayot", "Yangihayot", "Янгихаётский"),
    ("yashnobod", "Yashnobod", "Яшнабадский"),
    ("yunusobod", "Yunusobod", "Юнусабадский"),
]

# (code, lotin, rus, faol, [(spec_code, lotin, rus)])
CATEGORIES = [
    (
        "construction",
        "Qurilish",
        "Строительство",
        True,
        [
            ("general", "Umumiy ishchi", "Разнорабочий"),
            ("bricklayer", "G'isht teruvchi", "Каменщик"),
            ("plasterer", "Suvoqchi", "Штукатур"),
            ("painter", "Bo'yoqchi", "Маляр"),
            ("plumber", "Santexnik", "Сантехник"),
            ("electrician", "Elektrik", "Электрик"),
            ("master", "Usta", "Мастер"),
        ],
    ),
    (
        "cargo",
        "Yuk tashish",
        "Грузоперевозки",
        True,
        [
            ("loader", "Yukchi", "Грузчик"),
            ("warehouse", "Ombor ishchisi", "Складской рабочий"),
            ("driver_helper", "Haydovchi yordamchisi", "Помощник водителя"),
        ],
    ),
    (
        "cleaning",
        "Uy tozalash",
        "Уборка",
        True,
        [
            ("general", "Umumiy", "Общая уборка"),
            ("windows_tiles", "Deraza va kafel", "Окна и кафель"),
            ("after_repair", "Ta'mirdan keyin", "После ремонта"),
        ],
    ),
    (
        "other",
        "Boshqa",
        "Другое",
        True,
        [
            ("other", "Boshqa", "Другое"),
        ],
    ),
    (
        "childcare",
        "Bola qarash",
        "Присмотр за детьми",
        False,
        [
            ("age_0_1", "0–1 yosh", "0–1 год"),
            ("age_1_3", "1–3 yosh", "1–3 года"),
            ("age_3_7", "3–7 yosh", "3–7 лет"),
            ("age_7_plus", "7+ yosh", "7+ лет"),
        ],
    ),
    (
        "cooking",
        "Oshpazlik",
        "Кулинария",
        False,
        [
            ("home_cook", "Uy oshpazi", "Домашний повар"),
            ("event_helper", "Tadbir yordamchisi", "Помощник на мероприятии"),
        ],
    ),
    (
        "farming",
        "Dehqonchilik",
        "Сельхозработы",
        False,
        [
            ("field", "Dala", "Полевые работы"),
            ("garden", "Bog'", "Сад"),
            ("harvest", "Hosil yig'ish", "Сбор урожая"),
        ],
    ),
]


def _names(latn: str, ru: str) -> dict:
    return {"name_uz_latn": latn, "name_uz_cyrl": latin_to_cyrillic(latn), "name_ru": ru}


async def seed(session: AsyncSession) -> None:
    regions = {r.code: r for r in (await session.scalars(select(Region))).all()}
    for i, (code, latn, ru, active) in enumerate(REGIONS):
        if code not in regions:
            regions[code] = Region(code=code, is_active=active, sort_order=i, **_names(latn, ru))
            session.add(regions[code])
    await session.flush()

    tashkent = regions["tashkent_city"]
    existing = set((await session.scalars(select(District.code).where(District.region_id == tashkent.id))).all())
    for i, (code, latn, ru) in enumerate(TASHKENT_DISTRICTS):
        if code not in existing:
            session.add(District(region_id=tashkent.id, code=code, sort_order=i, **_names(latn, ru)))

    categories = {c.code: c for c in (await session.scalars(select(Category))).all()}
    for i, (code, latn, ru, active, specs) in enumerate(CATEGORIES):
        cat = categories.get(code)
        if cat is None:
            cat = Category(code=code, is_active=active, sort_order=i, **_names(latn, ru))
            session.add(cat)
            await session.flush()
        spec_codes = set(
            (await session.scalars(select(Specialization.code).where(Specialization.category_id == cat.id))).all()
        )
        for j, (s_code, s_latn, s_ru) in enumerate(specs):
            if s_code not in spec_codes:
                session.add(Specialization(category_id=cat.id, code=s_code, sort_order=j, **_names(s_latn, s_ru)))
    await session.flush()


async def _main() -> None:
    engine = make_engine(get_settings().database_url)
    async with make_sessionmaker(engine)() as session:
        await seed(session)
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
