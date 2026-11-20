"""Real-database checks (B1-A1-02). Skipped with a reason when PostgreSQL is unreachable."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

pytestmark = pytest.mark.db


async def test_database_answers(db_connection: AsyncConnection) -> None:
    result = await db_connection.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


async def test_postgis_is_installed(db_connection: AsyncConnection) -> None:
    version = (await db_connection.execute(text("SELECT PostGIS_Version()"))).scalar_one()
    assert version


async def test_changes_are_rolled_back_between_tests(db_connection: AsyncConnection) -> None:
    await db_connection.execute(text("CREATE TABLE IF NOT EXISTS _rollback_probe (id int)"))
    await db_connection.execute(text("INSERT INTO _rollback_probe VALUES (1)"))
    count = (await db_connection.execute(text("SELECT count(*) FROM _rollback_probe"))).scalar_one()
    assert count == 1


async def test_rollback_probe_left_nothing_behind(db_connection: AsyncConnection) -> None:
    exists = (
        await db_connection.execute(text("SELECT to_regclass('public._rollback_probe')"))
    ).scalar_one()
    assert exists is None
