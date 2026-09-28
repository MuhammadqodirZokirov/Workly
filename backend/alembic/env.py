import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from workly.infrastructure.config import get_settings
from workly.infrastructure.db import models  # noqa: F401  (jadvallarni ro'yxatdan o'tkazish)
from workly.infrastructure.db.base import Base

target_metadata = Base.metadata


def _url() -> str:
    return context.config.get_main_option("sqlalchemy.url") or get_settings().database_url


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    # Bazadagi begona jadvallarni (PostGIS: spatial_ref_sys, tiger geocoder va h.k.) e'tiborsiz qoldiramiz
    if type_ == "table" and reflected and compare_to is None:
        return False
    if type_ == "index" and reflected and compare_to is None and obj.table.name not in target_metadata.tables:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True, include_object=include_object
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as conn:
        await conn.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
