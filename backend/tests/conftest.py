"""Shared pytest fixtures (B1-A1-02).

Database tests use a separate ``dispatch_test`` database on the same PostgreSQL/PostGIS
server as the application. It is dropped, recreated and migrated to the latest Alembic revision
once per test run, so every run starts from the real schema with no leftover rows. The database
name never matches the application database, so tests cannot touch real data. If no server is reachable, tests marked ``db`` are skipped
with the reason; they are never reported as passed.

Connection settings come from the environment (never hard-coded):
  TEST_DATABASE_URL  full async URL of the test database, or
  DATABASE_URL       the application URL; its database name is replaced by TEST_DB_NAME.

Factories for users/vehicles/incidents are deliberately not here: the tables do not exist
yet and a factory without a model would be fake. They arrive with the model tasks.
"""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import psycopg2
import pytest
from alembic import command
from alembic.config import Config
from psycopg2 import sql
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.main import app

logger = logging.getLogger(__name__)

TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "dispatch_test")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _test_async_url() -> str | None:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    base = os.environ.get("DATABASE_URL")
    if not base:
        return None
    return make_url(base).set(database=TEST_DB_NAME).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """Recreate ``dispatch_test``, migrate it to head and return its async URL.

    Skips the requesting test, with a reason, when no server can be reached.
    """
    async_url = _test_async_url()
    if not async_url:
        pytest.skip("no DATABASE_URL / TEST_DATABASE_URL set; database tests not run")
    url = make_url(async_url)
    if url.database == make_url(os.environ.get("DATABASE_URL", "x:///")).database:
        pytest.fail("test database must not be the application database")

    admin_dsn = url.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    try:
        admin = psycopg2.connect(admin_dsn, connect_timeout=3)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable ({exc.__class__.__name__}); database tests not run")
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(url.database)))
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
            logger.info("recreated test database %s", url.database)
    finally:
        admin.close()

    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = async_url
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")  # 0001 enables PostGIS, then the schema and seeded settings
    yield async_url


@pytest.fixture
async def db_connection(test_database_url: str) -> AsyncIterator[AsyncConnection]:
    """A connection inside an outer transaction that is always rolled back."""
    engine = create_async_engine(test_database_url, poolclass=pool.NullPool)
    try:
        async with engine.connect() as conn:
            outer = await conn.begin()
            try:
                yield conn
            finally:
                await outer.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """ORM session bound to the rolled-back connection (nothing persists between tests)."""
    session = AsyncSession(bind=db_connection, expire_on_commit=False,
                           join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client calling the FastAPI app in-process (no network)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
