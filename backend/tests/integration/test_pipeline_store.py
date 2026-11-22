"""PostgresPipelineStore tests (B1-A1-19, contract C-6). Most run in the rolled-back test session; the
two-workers race and NOTIFY delivery need real commits and use a fresh throwaway database."""
from __future__ import annotations

import asyncio
import json
import select as io_select
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
from alembic import command
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Assignment, AuditLog, Caller, DuplicateCandidate, Incident, IncidentGroup, Recommendation, User, Vehicle
from app.schemas.ai import (
    AllocationResult,
    DuplicateCandidateResult,
    GeocodeResult,
    TriageResult,
    TrustAssessment,
    VehicleRecommendation,
)
from app.schemas.events import PipelineStage
from app.services.pipeline_store import PipelineStore, PostgresPipelineStore
from app.services.settings import defaults
from tests.integration.conftest import alembic_config, sync_dsn

pytestmark = pytest.mark.db
NOW = datetime.now(timezone.utc)
SUKKUR = (27.7052, 68.8574)


def pt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


@pytest.fixture
def store(db_session: AsyncSession) -> PostgresPipelineStore:
    @asynccontextmanager
    async def factory():
        yield db_session

    return PostgresPipelineStore(factory)


async def incident(db: AsyncSession, **cols) -> Incident:
    values = {"channel": "web", "original_text": "SIMULATED report", "settings_snapshot": defaults(), **cols}
    row = Incident(**values)
    db.add(row)
    await db.flush()
    return row


async def reload(db: AsyncSession, row: Incident) -> Incident:
    await db.refresh(row)
    return row


def triage(**kw) -> TriageResult:
    base = dict(language="English", language_confidence=0.9, incident_type="accident", type_confidence=0.9,
                severity="high", severity_confidence=0.9, victims_estimate=3, victims_confidence=0.8,
                location_words="near the market", has_real_details=True, vague_or_joking=False, missing_fields=[],
                overall_confidence=0.9, transcript_unclear=False, model="SIMULATED", prompt_version="v1", latency_ms=10)
    return TriageResult(**{**base, **kw})


def test_postgres_store_implements_the_contract() -> None:
    assert isinstance(PostgresPipelineStore(lambda: None), PipelineStore)


# ---------------------------------------------------------------- claiming jobs
async def test_claim_takes_the_most_urgent_then_oldest(store, db_session) -> None:
    low = await incident(db_session, severity="low", received_at=NOW - timedelta(minutes=9), pipeline_state="reallocate")
    new = await incident(db_session, received_at=NOW - timedelta(minutes=5))  # severity unknown, ranked like high
    critical = await incident(db_session, severity="critical", received_at=NOW, pipeline_state="reallocate")
    await incident(db_session, pipeline_state="done")
    order = [(await store.claim_next()).incident_id for _ in range(3)]
    assert order == [critical.incident_id, new.incident_id, low.incident_id]
    assert await store.claim_next() is None


async def test_claim_marks_processing_and_counts_attempts(store, db_session) -> None:
    gps_incident = await incident(db_session, caller_gps=pt(*SUKKUR), caller_id=None)
    job = await store.claim_next()
    assert (job.incident_id, job.job_type, job.attempts) == (gps_incident.incident_id, "pending", 1)
    assert (round(job.caller_gps.lat, 4), round(job.caller_gps.lon, 4)) == SUKKUR
    assert job.settings_snapshot["dup_auto_link"] == 85
    assert (await reload(db_session, gps_incident)).pipeline_state == "processing"


async def test_only_pending_and_reallocate_can_be_claimed(store) -> None:
    with pytest.raises(ValueError):
        await store.claim_next(frozenset({"processing"}))


async def test_stale_processing_jobs_are_requeued_or_failed(store, db_session) -> None:
    old = NOW - timedelta(minutes=30)
    retry = await incident(db_session, pipeline_state="processing", pipeline_attempts=1, pipeline_updated_at=old)
    give_up = await incident(db_session, pipeline_state="processing", pipeline_attempts=3, pipeline_updated_at=old)
    fresh = await incident(db_session, pipeline_state="processing", pipeline_attempts=1, pipeline_updated_at=NOW)
    assert await store.requeue_stale_jobs(older_than_minutes=10, max_attempts=3) == (1, 1)
    assert (await reload(db_session, retry)).pipeline_state == "pending"
    failed = await reload(db_session, give_up)
    assert failed.pipeline_state == "failed" and "ai_failed" in failed.review_reasons and failed.status == "needs_check"
    assert (await reload(db_session, fresh)).pipeline_state == "processing"


# ---------------------------------------------------------------- stage results
async def test_triage_sets_fields_status_and_audit(store, db_session) -> None:
    row = await incident(db_session)
    await store.save_triage(row.incident_id, triage())
    row = await reload(db_session, row)
    assert (row.incident_type, row.severity, row.victims_estimate, float(row.confidence), row.status) == \
           ("accident", "high", 3, 0.9, "triaged")
    assert row.ai_details["triage"]["model"] == "SIMULATED" and row.pipeline_updated_at is not None
    assert await db_session.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.incident_id == row.incident_id, AuditLog.action == "ai.triage")) == 1


async def test_low_confidence_uses_the_incidents_own_snapshot(store, db_session) -> None:
    strict = await incident(db_session, settings_snapshot={**defaults(), "triage_min_confidence": 95})
    await store.save_triage(strict.incident_id, triage(overall_confidence=0.9))
    strict = await reload(db_session, strict)
    assert "low_confidence" in strict.review_reasons and strict.status == "needs_check"


async def test_unknown_type_is_missing_info(store, db_session) -> None:
    row = await incident(db_session)
    await store.save_triage(row.incident_id, triage(incident_type=None, type_confidence=None, overall_confidence=0.5))
    row = await reload(db_session, row)
    assert {"missing_info", "low_confidence"} <= set(row.review_reasons) and row.status == "needs_check"


async def test_low_confidence_never_marks_a_report_fake(store, db_session) -> None:
    row = await incident(db_session)
    await store.save_triage(row.incident_id, triage(overall_confidence=0.05))
    assert (await reload(db_session, row)).status != "fake"


async def test_trust_review_queue_versus_urgent(store, db_session) -> None:
    signals = [{"code": "SIMULATED", "points": -30, "detail": "SIMULATED reason"}]
    low = await incident(db_session, status="triaged")
    urgent = await incident(db_session, status="triaged", severity="critical")
    await store.save_trust(low.incident_id, TrustAssessment(score=20, tier="low", signals=signals, action="review_queue"))
    await store.save_trust(urgent.incident_id, TrustAssessment(score=20, tier="low", signals=signals, action="urgent_with_warning"))
    low, urgent = await reload(db_session, low), await reload(db_session, urgent)
    assert low.status == "needs_check" and "low_trust" in low.review_reasons and low.trust_signals == signals
    assert urgent.status == "triaged" and urgent.review_reasons == ["low_trust_urgent"]  # never held back


async def test_geocode_fills_the_location_and_clears_location_unknown(store, db_session) -> None:
    row = await incident(db_session, location_source="unknown", review_reasons=["location_unknown"], location_text="market")
    await store.save_location(row.incident_id, GeocodeResult(lat=27.7, lon=68.85, source="gazetteer", matched_name="SIMULATED Market"))
    row = await reload(db_session, row)
    assert row.location_source == "text" and row.location is not None and row.review_reasons == []


async def test_voice_transcript_saved_once(store, db_session) -> None:
    row = await incident(db_session, original_text=None, audio_ref="audio/SIMULATED.wav", channel="voice")
    await store.save_transcript(row.incident_id, "SIMULATED transcript", True)
    await store.save_transcript(row.incident_id, "second transcript", False)  # ignored: text already set
    row = await reload(db_session, row)
    assert row.original_text == "SIMULATED transcript" and "transcript_unclear" in row.review_reasons


async def test_failure_keeps_the_report_for_manual_handling(store, db_session) -> None:
    row = await incident(db_session, pipeline_state="processing")
    await store.mark_stage_failed(row.incident_id, PipelineStage.TRIAGE, "LLM timeout")
    row = await reload(db_session, row)
    assert (row.pipeline_state, row.status) == ("failed", "needs_check") and "ai_failed" in row.review_reasons
    assert row.original_text == "SIMULATED report" and row.pipeline_error.startswith("triage:")


async def test_mark_done_and_heartbeat(store, db_session) -> None:
    row = await incident(db_session, pipeline_state="processing")
    await store.mark_done(row.incident_id)
    assert (await reload(db_session, row)).pipeline_state == "done"
    await store.heartbeat("worker-1", {"llm": "ready"})
    await store.heartbeat("worker-1", {"llm": "down"})
    assert (await db_session.execute(text("SELECT info FROM worker_heartbeats WHERE worker_id = 'worker-1'"))).scalar() == {"llm": "down"}


# ---------------------------------------------------------------- duplicates (UC-04)
async def test_candidates_respect_type_distance_time_and_open(store, db_session) -> None:
    me = await incident(db_session, incident_type="fire", location=pt(*SUKKUR), received_at=NOW)
    near = await incident(db_session, incident_type="fire", location=pt(27.7060, 68.8580), received_at=NOW - timedelta(minutes=10))
    await incident(db_session, incident_type="accident", location=pt(27.7060, 68.8580), received_at=NOW)  # other type
    await incident(db_session, incident_type="fire", location=pt(27.7200, 68.8574), received_at=NOW)  # ~1.6 km away
    await incident(db_session, incident_type="fire", location=pt(27.7060, 68.8580), received_at=NOW - timedelta(minutes=20))  # too old
    await incident(db_session, incident_type="fire", location=pt(27.7060, 68.8580), received_at=NOW, status="fake")
    await incident(db_session, incident_type="fire", location=pt(27.7060, 68.8580), received_at=NOW, status="closed")
    found = await store.find_duplicate_candidates(me.incident_id, 300, 15)
    assert [c.incident_id for c in found] == [near.incident_id]


async def test_no_candidates_without_location_or_type(store, db_session) -> None:
    me = await incident(db_session, incident_type=None, location=pt(*SUKKUR))
    assert await store.find_duplicate_candidates(me.incident_id, 300, 15) == []


async def test_independent_reports_are_distinct_known_callers(store, db_session) -> None:
    callers = [Caller(phone_number=f"+92-SIM-{i}") for i in range(3)]
    db_session.add_all(callers)
    await db_session.flush()
    me = await incident(db_session, incident_type="fire", location=pt(*SUKKUR), caller_id=callers[0].caller_id)
    for caller_id in (callers[0].caller_id, callers[1].caller_id, callers[1].caller_id, callers[2].caller_id, None):
        await incident(db_session, incident_type="fire", location=pt(27.7055, 68.8576), caller_id=caller_id)
    assert await store.count_independent_nearby(me.incident_id, 300, 15) == 2


async def test_duplicate_results_auto_link_groups_and_possible_warns(store, db_session) -> None:
    me, other, third = [await incident(db_session, status="triaged") for _ in range(3)]
    await store.save_duplicate_results(me.incident_id, [
        DuplicateCandidateResult(candidate_incident_id=other.incident_id, distance_m=50, time_diff_s=60, s_dist=0.9,
                                 s_time=0.9, s_meaning=0.95, match_confidence=93, decision="auto_linked"),
        DuplicateCandidateResult(candidate_incident_id=third.incident_id, distance_m=200, time_diff_s=600, s_dist=0.5,
                                 s_time=0.5, s_meaning=0.7, match_confidence=70, decision="possible"),
    ])
    me, other, third = [await reload(db_session, x) for x in (me, other, third)]
    assert me.group_id is not None and me.group_id == other.group_id and third.group_id is None
    assert (await db_session.get(IncidentGroup, me.group_id)).report_count == 2
    assert (me.status, other.status) == ("triaged", "triaged")  # linking never hides or closes (rule 4)
    assert "possible_duplicate" in me.review_reasons and me.status != "needs_check"


async def test_a_dispatcher_decision_is_never_overwritten(store, db_session) -> None:
    me, other = await incident(db_session), await incident(db_session)
    db_session.add(DuplicateCandidate(incident_id=me.incident_id, candidate_incident_id=other.incident_id,
                                      match_confidence=70, decision="rejected"))
    await db_session.flush()
    await store.save_duplicate_results(me.incident_id, [DuplicateCandidateResult(
        candidate_incident_id=other.incident_id, distance_m=10, time_diff_s=10, s_dist=1, s_time=1, s_meaning=1,
        match_confidence=99, decision="auto_linked")])
    decision = await db_session.scalar(select(DuplicateCandidate.decision).where(DuplicateCandidate.incident_id == me.incident_id))
    assert decision == "rejected"


# ---------------------------------------------------------------- vehicles and recommendations (UC-05)
async def _vehicle(db: AsyncSession, plate: str, *, on_duty: bool = True, seen_s_ago: int = 5, status: str = "available") -> Vehicle:
    driver = User(full_name="SIMULATED Driver", username=f"drv_{plate}", password_hash="x", role="driver", on_duty=on_duty)
    db.add(driver)
    await db.flush()
    v = Vehicle(vehicle_type="ambulance", plate_number=plate, driver_id=driver.user_id, status=status,
                last_location=pt(*SUKKUR), last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=seen_s_ago), patient_capacity=2)
    db.add(v)
    await db.flush()
    return v


async def test_available_vehicles_rules(store, db_session) -> None:
    ok = await _vehicle(db_session, "SIM-OK")
    await _vehicle(db_session, "SIM-OFF", on_duty=False)
    await _vehicle(db_session, "SIM-LOST", seen_s_ago=600)
    await _vehicle(db_session, "SIM-BUSY", status="assigned")
    locked = await _vehicle(db_session, "SIM-LOCKED")
    dispatcher = User(full_name="SIMULATED D", username="disp_x", password_hash="x", role="dispatcher")
    db_session.add(dispatcher)
    inc = await incident(db_session)
    await db_session.flush()
    db_session.add(Assignment(incident_id=inc.incident_id, vehicle_id=locked.vehicle_id, approved_by=dispatcher.user_id))
    await db_session.flush()
    found = await store.list_available_vehicles(frozenset({"ambulance"}))
    assert [v.vehicle_id for v in found] == [ok.vehicle_id]
    assert await store.list_available_vehicles(frozenset({"fire_truck"})) == []


async def test_recommendation_rounds_and_no_locking(store, db_session) -> None:
    v = await _vehicle(db_session, "SIM-REC")
    row = await incident(db_session, status="triaged")
    rec = VehicleRecommendation(vehicle_id=v.vehicle_id, vehicle_type="ambulance", rank=1, eta_seconds=300,
                                distance_meters=2000, eta_is_approximate=True, is_spare=False)
    result = AllocationResult(needed={"ambulance": 1}, victims_unknown_check=False, shortage={"ambulance": 0},
                              recommendations=[rec], routing_mode="straight_line")
    await store.save_recommendations(row.incident_id, result)
    await store.save_recommendations(row.incident_id, result)
    rows = (await db_session.scalars(select(Recommendation).where(Recommendation.incident_id == row.incident_id)
                                     .order_by(Recommendation.batch_no))).all()
    assert [(r.batch_no, r.is_current) for r in rows] == [(1, False), (2, True)]
    row = await reload(db_session, row)
    assert row.allocation_summary["routing_mode"] == "straight_line" and row.allocation_summary["batch_no"] == 2
    assert "vehicle_shortage" in row.review_reasons
    assert (await db_session.get(Vehicle, v.vehicle_id)).status == "available"  # recommending never locks (rule 6)
    assert await db_session.scalar(select(func.count()).select_from(Assignment)) == 0


# ---------------------------------------------------------------- real commits: race and NOTIFY
@pytest.fixture
def fresh_url(migration_db: str) -> str:
    command.upgrade(alembic_config(migration_db), "head")  # sync fixture: Alembic runs its own event loop
    return migration_db


@pytest.fixture
async def fresh(fresh_url: str):
    migration_db = fresh_url
    engine = create_async_engine(migration_db)
    try:
        yield migration_db, async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_two_workers_never_claim_the_same_incident(fresh) -> None:
    url, sessions = fresh
    async with sessions() as db:
        for _ in range(30):
            db.add(Incident(channel="web", original_text="SIMULATED", settings_snapshot={}))
        await db.commit()
    workers = [PostgresPipelineStore(sessions), PostgresPipelineStore(sessions)]

    async def drain(store: PostgresPipelineStore) -> list[int]:
        claimed = []
        while (job := await store.claim_next()) is not None:
            claimed.append(job.incident_id)
            await asyncio.sleep(0)
        return claimed

    a, b = await asyncio.gather(drain(workers[0]), drain(workers[1]))
    assert not set(a) & set(b) and len(a) + len(b) == 30  # every job exactly once (either worker may get more)


async def test_a_row_locked_by_one_worker_is_skipped_by_the_other(fresh) -> None:
    """Deterministic SKIP LOCKED check: while worker A holds the oldest job's row lock, worker B gets the next one."""
    url, sessions = fresh
    async with sessions() as db:
        first = Incident(channel="web", original_text="SIMULATED 1", settings_snapshot={}, received_at=NOW - timedelta(minutes=2))
        second = Incident(channel="web", original_text="SIMULATED 2", settings_snapshot={}, received_at=NOW - timedelta(minutes=1))
        db.add_all([first, second])
        await db.commit()
    holder = psycopg2.connect(sync_dsn(url))
    try:
        holder.cursor().execute("SELECT 1 FROM incidents WHERE incident_id = %s FOR UPDATE", (first.incident_id,))
        # a claim that waited for the lock instead of skipping it would never finish: fail after 5 s
        job = await asyncio.wait_for(PostgresPipelineStore(sessions).claim_next(), timeout=5)
        assert job.incident_id == second.incident_id  # the locked, older row was skipped, not waited for
    finally:
        holder.rollback()
        holder.close()
    job = await PostgresPipelineStore(sessions).claim_next()
    assert job.incident_id == first.incident_id


async def test_notifications_are_sent_on_commit(fresh) -> None:
    url, sessions = fresh
    listener = psycopg2.connect(sync_dsn(url))
    listener.autocommit = True
    listener.cursor().execute("LISTEN incident_events; LISTEN report_pending")
    try:
        from app.schemas.report import ReportIn
        from app.services import intake

        async with sessions() as db:
            created, _ = await intake.create_report(db, ReportIn(description="SIMULATED report"))
            await db.commit()
        store = PostgresPipelineStore(sessions)
        await store.save_triage(created.incident_id, triage(overall_confidence=0.2))
        got: list[tuple[str, str]] = []
        deadline = asyncio.get_running_loop().time() + 5
        wanted = {"report_pending", "incident.updated", "review.item_added"}
        while asyncio.get_running_loop().time() < deadline:
            io_select.select([listener], [], [], 0.2)
            listener.poll()
            got += [(n.channel, n.payload) for n in listener.notifies]
            listener.notifies.clear()
            seen = {c for c, _ in got if c == "report_pending"} | {json.loads(p)["event"] for c, p in got if c == "incident_events"}
            if wanted <= seen:
                break
    finally:
        listener.close()
    assert ("report_pending", str(created.incident_id)) in got
    events = [json.loads(p)["event"] for c, p in got if c == "incident_events"]
    assert "incident.updated" in events and "review.item_added" in events
    assert all(set(json.loads(p)) == {"event", "incident_id"} for c, p in got if c == "incident_events")
