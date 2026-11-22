"""End to end on the real database (B1-A2-13/14 with B1-A1-19): a saved report is claimed, triaged,
scored and given recommendations through ``PostgresPipelineStore``. Fake model only (SIMULATED)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import Orchestrator
from app.agents.triage import TriageAgent
from app.llm.fake import FakeLLMClient
from app.models import Assignment, AuditLog, Incident, Recommendation, User, Vehicle
from app.schemas.enums import PipelineState
from app.services.pipeline_store import PostgresPipelineStore
from app.services.settings import defaults
from tests.unit.agents.fakes import triage_reply

pytestmark = pytest.mark.db
SUKKUR = (27.7052, 68.8574)
NOW = datetime.now(timezone.utc)


def pt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


@pytest.fixture
def store(db_session: AsyncSession) -> PostgresPipelineStore:
    @asynccontextmanager
    async def factory():
        yield db_session

    return PostgresPipelineStore(factory)


async def ambulance(db: AsyncSession, plate: str, km: float) -> Vehicle:
    driver = User(full_name="SIMULATED Driver", username=f"drv_{plate}", password_hash="x", role="driver", on_duty=True)
    db.add(driver)
    await db.flush()
    v = Vehicle(vehicle_type="ambulance", plate_number=plate, driver_id=driver.user_id, status="available",
                last_location=pt(SUKKUR[0] + km / 111.2, SUKKUR[1]), last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=5),
                patient_capacity=2)
    db.add(v)
    await db.flush()
    return v


async def report(db: AsyncSession, **cols) -> Incident:
    row = Incident(channel="web", original_text="SIMULATED: bus accident near Clock Tower, 3 people hurt",
                   caller_gps=pt(*SUKKUR), settings_snapshot=defaults(), **cols)
    db.add(row)
    await db.flush()
    return row


async def test_a_saved_report_is_triaged_scored_and_gets_recommendations(store, db_session) -> None:
    near, far = await ambulance(db_session, "SIM-E2E-1", 1), await ambulance(db_session, "SIM-E2E-2", 4)
    row = await report(db_session)
    job = await store.claim_next(frozenset({PipelineState.PENDING}))
    assert job.incident_id == row.incident_id

    outcome = await Orchestrator(store, TriageAgent(FakeLLMClient([triage_reply(victims_estimate=3)]))).run(job)
    assert outcome.done

    await db_session.refresh(row)
    assert (row.pipeline_state, row.status) == ("done", "triaged")
    assert (row.incident_type, row.severity, row.victims_estimate) == ("accident", "high", 3)
    assert row.location_source == "gps" and row.trust_tier == "medium" and row.trust_score == 60
    assert row.original_text.startswith("SIMULATED: bus accident")  # the report itself is never changed
    recs = (await db_session.scalars(select(Recommendation).where(Recommendation.incident_id == row.incident_id)
                                     .order_by(Recommendation.rank))).all()
    assert [r.vehicle_id for r in recs] == [near.vehicle_id, far.vehicle_id] and all(r.eta_is_approximate for r in recs)
    actions = set(await db_session.scalars(select(AuditLog.action).where(AuditLog.incident_id == row.incident_id)))
    assert {"ai.geocode", "ai.triage", "ai.trust", "ai.allocation"} <= actions  # safety rule 9
    assert (await db_session.get(Vehicle, near.vehicle_id)).status == "available"  # never locked (rule 6)
    assert await db_session.scalar(select(func.count()).select_from(Assignment)) == 0  # never dispatched (rule 2)


async def test_low_confidence_from_the_model_means_the_dispatcher_must_check_tc08(store, db_session) -> None:
    row = await report(db_session)
    job = await store.claim_next(frozenset({PipelineState.PENDING}))
    await Orchestrator(store, TriageAgent(FakeLLMClient([triage_reply(overall_confidence=0.4)]))).run(job)
    await db_session.refresh(row)
    assert row.status == "needs_check" and "low_confidence" in row.review_reasons and row.status != "fake"


async def test_missing_type_means_more_information_needed_tc07(store, db_session) -> None:
    row = await report(db_session)
    job = await store.claim_next(frozenset({PipelineState.PENDING}))
    reply = triage_reply(incident_type=None, type_confidence=None)
    await Orchestrator(store, TriageAgent(FakeLLMClient([reply]))).run(job)
    await db_session.refresh(row)
    assert row.status == "needs_check" and "missing_info" in row.review_reasons


async def test_a_model_failure_keeps_the_report_for_manual_dispatch(store, db_session) -> None:
    row = await report(db_session)
    job = await store.claim_next(frozenset({PipelineState.PENDING}))
    outcome = await Orchestrator(store, TriageAgent(FakeLLMClient(["broken", "broken"]))).run(job)
    await db_session.refresh(row)
    assert outcome.failed == "triage"
    assert (row.pipeline_state, row.status) == ("failed", "needs_check") and "ai_failed" in row.review_reasons
    assert row.trust_tier is not None and "ai_unavailable" in {s["code"] for s in row.trust_signals}  # D-035
    assert row.original_text.startswith("SIMULATED")  # nothing lost (safety rule 7)
