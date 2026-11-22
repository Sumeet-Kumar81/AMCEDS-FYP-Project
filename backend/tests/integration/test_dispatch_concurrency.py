"""TC-22 on a real database with real commits (B1-A1-25): two dispatchers approving the same vehicle at
the same moment, 50 times — exactly one succeeds each time, the other gets 409 ``vehicle_locked`` with
the next best vehicle, and no vehicle ever has two open assignments. Plus the last-line guard: the
partial unique index refuses a second open assignment even without the service. SIMULATED data."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from alembic import command
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Assignment, Incident, Recommendation, User, Vehicle
from app.schemas.dispatch import DispatchIn
from app.services.dispatch import DispatchError, approve
from tests.integration.conftest import alembic_config

pytestmark = pytest.mark.db
ROUNDS = 50


def pt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


@pytest.fixture
def fresh_url(migration_db: str) -> str:
    command.upgrade(alembic_config(migration_db), "head")  # sync fixture: Alembic runs its own event loop
    return migration_db


@pytest.fixture
async def sessions(fresh_url: str):
    engine = create_async_engine(fresh_url, pool_size=10)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def setup(sessions):
    async with sessions() as db:
        d1 = User(full_name="SIMULATED Dispatcher A", username="sim_disp_a", password_hash="x", role="dispatcher")
        d2 = User(full_name="SIMULATED Dispatcher B", username="sim_disp_b", password_hash="x", role="dispatcher")
        drivers = [User(full_name=f"SIMULATED Driver {i}", username=f"sim_drv_{i}", password_hash="x", role="driver",
                        on_duty=True) for i in (1, 2)]
        db.add_all([d1, d2, *drivers])
        await db.flush()
        target = Vehicle(vehicle_type="ambulance", plate_number="SIM-RACE-1", driver_id=drivers[0].user_id,
                         last_location=pt(27.70, 68.85), last_seen_at=datetime.now(timezone.utc))
        spare = Vehicle(vehicle_type="ambulance", plate_number="SIM-RACE-2", driver_id=drivers[1].user_id,
                        last_location=pt(27.71, 68.85), last_seen_at=datetime.now(timezone.utc))
        a = Incident(channel="web", original_text="SIMULATED A", status="triaged", severity="critical", location=pt(27.7, 68.85))
        b = Incident(channel="web", original_text="SIMULATED B", status="triaged", severity="critical", location=pt(27.7, 68.85))
        db.add_all([target, spare, a, b])
        await db.flush()
        for inc in (a, b):
            db.add_all([Recommendation(incident_id=inc.incident_id, vehicle_id=target.vehicle_id, rank=1, eta_seconds=60,
                                       distance_meters=500, vehicle_type="ambulance", eta_is_approximate=True),
                        Recommendation(incident_id=inc.incident_id, vehicle_id=spare.vehicle_id, rank=2, eta_seconds=120,
                                       distance_meters=900, vehicle_type="ambulance", eta_is_approximate=True)])
        await db.commit()
        return d1, d2, target, spare, a, b


async def attempt(sessions, incident_id: int, vehicle_id: int, dispatcher: User):
    async with sessions() as db:
        try:
            out = await approve(db, incident_id, DispatchIn(vehicle_ids=[vehicle_id]), dispatcher)
            await db.commit()
            return ("ok", [x.assignment_id for x in out])
        except DispatchError as err:
            await db.rollback()
            return (err.code, err.details)


async def test_tc22_two_dispatchers_one_vehicle_50_rounds(sessions) -> None:
    d1, d2, target, spare, a, b = await setup(sessions)
    for _ in range(ROUNDS):
        results = await asyncio.gather(attempt(sessions, a.incident_id, target.vehicle_id, d1),
                                       attempt(sessions, b.incident_id, target.vehicle_id, d2))
        codes = sorted(r[0] for r in results)
        assert codes == ["ok", "vehicle_locked"], results
        loser = next(r for r in results if r[0] == "vehicle_locked")
        assert loser[1]["next_best"] == [spare.vehicle_id]  # the other dispatcher is offered the next best
        async with sessions() as db:
            open_count = await db.scalar(select(func.count()).select_from(Assignment)
                                         .where(Assignment.vehicle_id == target.vehicle_id, Assignment.status == "approved"))
            assert open_count == 1
            # free the vehicle for the next round (as a completed trip would)
            await db.execute(text("UPDATE assignments SET status = 'completed', completed_at = now() WHERE status = 'approved'"))
            await db.execute(text("UPDATE vehicles SET status = 'available'"))
            await db.execute(text("UPDATE incidents SET status = 'triaged'"))
            await db.commit()
    async with sessions() as db:
        total = await db.scalar(select(func.count()).select_from(Assignment).where(Assignment.vehicle_id == target.vehicle_id))
        assert total == ROUNDS  # one winner per round, never two


async def test_the_database_refuses_a_second_open_assignment_on_its_own(sessions) -> None:
    d1, _, target, _, a, b = await setup(sessions)
    async with sessions() as db:
        db.add(Assignment(incident_id=a.incident_id, vehicle_id=target.vehicle_id, approved_by=d1.user_id))
        await db.commit()
    async with sessions() as db:
        db.add(Assignment(incident_id=b.incident_id, vehicle_id=target.vehicle_id, approved_by=d1.user_id))
        with pytest.raises(IntegrityError, match="uq_assignments_open_vehicle"):
            await db.commit()
