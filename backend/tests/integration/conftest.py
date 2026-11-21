"""Fixtures for database integration tests that need their own throwaway databases (B1-A1-06…11).

These databases are created fresh and deleted after use, so the tests never touch the application
database or ``dispatch_test``. Everything is skipped, with a reason, if PostgreSQL is unreachable.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg2
import pytest
from alembic import command
from alembic.config import Config
from psycopg2 import sql
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND / "alembic.ini"


def admin_dsn(async_url: str) -> str:
    return make_url(async_url).set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)


def sync_dsn(async_url: str) -> str:
    return make_url(async_url).set(drivername="postgresql").render_as_string(hide_password=False)


def recreate_database(async_url: str, *, drop_only: bool = False) -> None:
    name = make_url(async_url).database
    conn = psycopg2.connect(admin_dsn(async_url), connect_timeout=3)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
            if not drop_only:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        conn.close()


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False  # keep pytest's logging setup
    return cfg


def query(url: str, statement: str, params: tuple | None = None) -> list[tuple]:
    conn = psycopg2.connect(sync_dsn(url), connect_timeout=3)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(statement, params)
            return cur.fetchall() if cur.description else []
    finally:
        conn.close()


def _throwaway(name: str) -> Iterator[str]:
    base = os.environ.get("DATABASE_URL")
    if not base:
        pytest.skip("no DATABASE_URL set; database tests not run")
    url = make_url(base).set(database=name).render_as_string(hide_password=False)
    try:
        recreate_database(url)
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL not reachable ({exc.__class__.__name__}); database tests not run")
    try:
        yield url
    finally:
        recreate_database(url, drop_only=True)


@pytest.fixture
def migration_db() -> Iterator[str]:
    """Async URL of a brand-new, empty database (no PostGIS, no tables)."""
    yield from _throwaway("dispatch_migrations_test")


@pytest.fixture(scope="module")
def schema_db() -> Iterator[str]:
    """Async URL of a throwaway database migrated to head, shared by one test module."""
    for url in _throwaway("dispatch_schema_test"):
        command.upgrade(alembic_config(url), "head")
        yield url


@pytest.fixture
def db(schema_db: str) -> Iterator[psycopg2.extensions.connection]:
    """A psycopg2 connection to the migrated database inside a transaction that is always rolled back."""
    conn = psycopg2.connect(sync_dsn(schema_db), connect_timeout=3)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
