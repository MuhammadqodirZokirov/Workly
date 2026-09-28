from fastapi import APIRouter

from workly.application.catalog import CatalogService

from ..deps import DbDep
from ..schemas import CategoryOut, DistrictOut, Names, RegionOut, SpecializationOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def categories(db: DbDep):
    return [
        CategoryOut(
            id=c.id,
            code=c.code,
            name=Names.of(c),
            specializations=[
                SpecializationOut(id=s.id, code=s.code, name=Names.of(s)) for s in c.specializations if s.is_active
            ],
        )
        for c in await CatalogService(db).categories()
    ]


@router.get("/regions", response_model=list[RegionOut])
async def regions(db: DbDep):
    return [RegionOut(id=r.id, code=r.code, name=Names.of(r)) for r in await CatalogService(db).regions()]


@router.get("/districts", response_model=list[DistrictOut])
async def districts(db: DbDep, region_id: int | None = None):
    return [
        DistrictOut(id=d.id, region_id=d.region_id, code=d.code, name=Names.of(d))
        for d in await CatalogService(db).districts(region_id)
    ]
