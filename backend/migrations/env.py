"""Alembic environment: async (asyncpg), PostGIS-aware (B1-A1-06).

* The URL comes from ``config.attributes["database_url"]`` (used by the tests) or else from the
  application settings, which read ``DATABASE_URL`` from the environment / ``.env``. It is never
  stored in ``alembic.ini``.
* ``target_metadata`` is the application's ``Base.metadata``; models register themselves when
  ``app.models`` is imported.
* GeoAlchemy2's Alembic helpers make geometry columns and their spatial indexes autogenerate
  correctly. Tables owned by PostGIS (``spatial_ref_sys``) are ignored.
* The migration connection uses ``search_path = public``. The postgis/postgis image sets the database
  search path to ``public, topology, tiger``; without this, autogenerate would see the tiger tables as
  ours and generate a migration that DROPS them (found on the local database in B1-A1-06).
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (registers the models on Base.metadata)
from app.core.config import get_settings
from app.core.db import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

POSTGIS_OWNED_TABLES = frozenset({"spatial_ref_sys"})
MIGRATION_SEARCH_PATH = "public"


def include_object(obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any) -> bool:
    if type_ == "table" and name in POSTGIS_OWNED_TABLES:
        return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def database_url() -> str:
    return config.attributes.get("database_url") or get_settings().database_url


def _configure(**kwargs: Any) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Write SQL instead of running it (``alembic upgrade head --sql``)."""
    _configure(url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(
        database_url(),
        poolclass=pool.NullPool,
        connect_args={"server_settings": {"search_path": MIGRATION_SEARCH_PATH}},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_sync)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
