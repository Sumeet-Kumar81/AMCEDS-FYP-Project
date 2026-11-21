"""Contract C-6: the AI worker's only door to the database (interface B1-A1-05, PostgreSQL implementation B1-A1-19).

This module defines *what* the worker may read and write (the ``PipelineStore`` protocol, C-6) and,
since B1-A1-19, ``PostgresPipelineStore``, its PostgreSQL implementation. The AI agents can be tested against a fake that
implements this same ``PipelineStore`` protocol. Nothing here returns made-up data.

Rules every implementation must follow (SDS §3.1, §4.3, D-010, D-011, safety rules):
  * Jobs are claimed with ``SELECT ... FOR UPDATE SKIP LOCKED`` on ``incidents.pipeline_state``;
    claiming sets ``processing`` and adds 1 to ``pipeline_attempts``.
  * Every stage result is saved before the next stage starts, so a later failure cannot erase it.
    The original report text and audio are never changed.
  * Every write sends ``NOTIFY incident_events`` with a ``NotifyPayload`` (event name + incident id).
  * Every AI result written here is also written to the audit log (NFR-S9).
  * The worker never sets ``dispatched``, never creates assignments and never locks a vehicle.
    ``list_available_vehicles`` only reads; vehicles are locked only at dispatcher approval.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.schemas.ai import (
    AllocationResult,
    DuplicateCandidateResult,
    GeocodeResult,
    GeoPoint,
    TriageResult,
    TrustAssessment,
)
from app.schemas.enums import Channel, IncidentType, PipelineState, VehicleType
from app.schemas.events import PipelineStage

CLAIMABLE_JOB_TYPES = frozenset({PipelineState.PENDING, PipelineState.REALLOCATE})
"""``pipeline_state`` values the worker picks up. ("retrust" is not an approved state; see B1-A2-15.)"""


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PipelineJob(_Row):
    """A claimed incident and the raw inputs the pipeline needs (SDS Table 5.2 columns)."""

    incident_id: int
    job_type: PipelineState
    attempts: int = Field(ge=1)
    channel: Channel
    received_at: AwareDatetime
    original_text: str | None
    audio_ref: str | None
    location_text: str | None
    caller_gps: GeoPoint | None
    caller_id: int | None
    settings_snapshot: dict[str, Any]  # settings in force when the report arrived (UC-12)

    @field_validator("job_type")
    @classmethod
    def _claimable_only(cls, value: PipelineState) -> PipelineState:
        if value not in CLAIMABLE_JOB_TYPES:
            raise ValueError("a job is either 'pending' or 'reallocate'")
        return value


class CandidateRow(_Row):
    """An open incident of the same type inside the distance and time window (UC-04)."""

    incident_id: int
    incident_type: IncidentType
    received_at: AwareDatetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    original_text: str | None
    caller_id: int | None


class CallerHistory(_Row):
    """Earlier outcomes for the caller or device (SDS Table 5.1), used by the Trust Scorer (SRS Table 7.3.1)."""

    caller_id: int
    real_count: int = Field(ge=0)
    fake_count: int = Field(ge=0)
    flagged_until: AwareDatetime | None


class VehicleRow(_Row):
    """A vehicle with status ``available`` and a known position (SDS Table 5.5). Reading it never locks it."""

    vehicle_id: int
    vehicle_type: VehicleType
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    patient_capacity: int = Field(ge=0)
    station_name: str | None


@runtime_checkable
class PipelineStore(Protocol):
    """Everything the AI worker may do with the database. Implemented in B1-A1-19."""

    async def claim_next(self, job_types: frozenset[PipelineState] = CLAIMABLE_JOB_TYPES) -> PipelineJob | None:
        """Claim the oldest waiting job (SKIP LOCKED) and mark it ``processing``; ``None`` if there is none."""
        ...

    async def save_transcript(self, incident_id: int, transcript: str, transcript_unclear: bool) -> None:
        """Store the speech-to-text result as ``original_text`` for a voice report (the audio stays as saved)."""
        ...

    async def save_location(self, incident_id: int, result: GeocodeResult) -> None:
        """Store the incident location and ``location_source`` (gazetteer/nominatim -> text, gps -> gps)."""
        ...

    async def save_triage(self, incident_id: int, result: TriageResult) -> None:
        """Store type, severity, victims, confidence and review reasons; full result into ``ai_details``."""
        ...

    async def save_trust(self, incident_id: int, assessment: TrustAssessment) -> None:
        """Store score, tier and ``trust_signals``. The action is inside the assessment."""
        ...

    async def find_duplicate_candidates(
        self, incident_id: int, distance_m: int, window_min: int
    ) -> list[CandidateRow]:
        """Open incidents of the same type within ``distance_m`` metres and ``window_min`` minutes."""
        ...

    async def count_independent_nearby(self, incident_id: int, distance_m: int, window_min: int) -> int:
        """Reports of the same type nearby from a different caller or device (D-012)."""
        ...

    async def get_caller_history(self, caller_id: int) -> CallerHistory | None:
        """The caller's earlier outcomes; ``None`` if the caller is unknown."""
        ...

    async def save_duplicate_results(self, incident_id: int, results: list[DuplicateCandidateResult]) -> None:
        """Store matches in ``duplicate_candidates``. Auto-linking never hides or closes an incident."""
        ...

    async def list_available_vehicles(self, types: frozenset[VehicleType]) -> list[VehicleRow]:
        """Available vehicles of the given types with a known position. Read only: never locks."""
        ...

    async def save_recommendations(self, incident_id: int, result: AllocationResult) -> None:
        """Store a new recommendation round (``batch_no`` + 1, older rounds ``is_current = false``)."""
        ...

    async def mark_stage_failed(self, incident_id: int, stage: PipelineStage, error: str) -> None:
        """Record the failure, set review reason ``ai_failed``; the dispatcher continues by hand."""
        ...

    async def mark_done(self, incident_id: int) -> None:
        """Set ``pipeline_state = done``."""
        ...

    async def heartbeat(self, worker_id: str, info: dict[str, Any]) -> None:
        """Update ``worker_heartbeats`` (readiness of the language model and speech-to-text)."""
        ...


# ====================================================================== PostgreSQL implementation (B1-A1-19)
import json  # noqa: E402
import logging  # noqa: E402
from collections.abc import Callable  # noqa: E402
from contextlib import AbstractAsyncContextManager  # noqa: E402

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.schemas.assignment import OPEN_ASSIGNMENT_STATUSES  # noqa: E402
from app.schemas.events import EventName, NotifyPayload, NOTIFY_CHANNEL  # noqa: E402
from app.services.audit import AuditAction, record  # noqa: E402
from app.services.settings import REGISTRY, get_value  # noqa: E402

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

NEEDS_CHECK_REASONS = ("low_confidence", "missing_info", "location_unknown", "ai_failed", "low_trust")
"""Review reasons that put an incident in ``needs_check`` (the dispatcher must look). Warnings such as
``possible_duplicate``, ``low_trust_urgent`` and ``vehicle_shortage`` are shown but never hold a report
back: high/critical reports are never held by trust or duplicate checks (safety rule 3)."""
OPEN_INCIDENT_STATUSES_EXCLUDED = ("closed", "fake")
_OPEN_ASSIGNMENTS = [s.value for s in OPEN_ASSIGNMENT_STATUSES]

# A new report has no severity yet; it is ranked with "high" so it is never starved behind low ones.
_SEVERITY_RANK = "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 1 END"


def _jsonable(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


class PostgresPipelineStore:
    """``PipelineStore`` on PostgreSQL. Every public method uses its own session and commits, so each
    pipeline stage is saved before the next one starts. Inputs are re-validated with their C-2 schema."""

    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        if session_factory is None:
            from app.core.db import SessionLocal

            session_factory = SessionLocal
        self._sessions = session_factory

    # ------------------------------------------------------------------ helpers
    @staticmethod
    async def _notify(db: AsyncSession, event: EventName, incident_id: int) -> None:
        payload = NotifyPayload(event=event, incident_id=incident_id).model_dump_json()
        await db.execute(text("SELECT pg_notify(:c, :p)"), {"c": NOTIFY_CHANNEL, "p": payload})

    @staticmethod
    async def _reasons(db: AsyncSession, incident_id: int, add: list[str] = (), remove: list[str] = ()) -> list[str]:
        """Add/remove review reasons; return the reasons that were newly added."""
        before = set(await db.scalar(text("SELECT review_reasons FROM incidents WHERE incident_id = :i"), {"i": incident_id}) or [])
        after = (before - set(remove)) | set(add)
        await db.execute(text("UPDATE incidents SET review_reasons = :r WHERE incident_id = :i"),
                         {"r": sorted(after), "i": incident_id})
        return sorted(set(add) - before)

    @staticmethod
    async def _refresh_status(db: AsyncSession, incident_id: int) -> None:
        """triaged / needs_check from the review reasons; never touches dispatched, on_scene, closed or fake."""
        await db.execute(text(
            "UPDATE incidents SET status = CASE WHEN review_reasons && CAST(:check AS text[]) THEN 'needs_check' ELSE 'triaged' END "
            "WHERE incident_id = :i AND status IN ('new', 'triaged', 'needs_check')"
        ), {"check": list(NEEDS_CHECK_REASONS), "i": incident_id})

    async def _updated(self, db: AsyncSession, incident_id: int, added_reasons: list[str]) -> None:
        await db.execute(text("UPDATE incidents SET pipeline_updated_at = now() WHERE incident_id = :i"), {"i": incident_id})
        await self._notify(db, EventName.INCIDENT_UPDATED, incident_id)
        if added_reasons:
            await self._notify(db, EventName.REVIEW_ITEM_ADDED, incident_id)

    @staticmethod
    async def _merge_ai_details(db: AsyncSession, incident_id: int, key: str, value: Any) -> None:
        await db.execute(text(
            "UPDATE incidents SET ai_details = coalesce(ai_details, '{}'::jsonb) || jsonb_build_object(CAST(:k AS text), CAST(:v AS jsonb)) "
            "WHERE incident_id = :i"
        ), {"k": key, "v": json.dumps(value), "i": incident_id})

    # ------------------------------------------------------------------ jobs
    async def claim_next(self, job_types: frozenset[PipelineState] = CLAIMABLE_JOB_TYPES) -> PipelineJob | None:
        types = sorted(PipelineState(t).value for t in job_types)
        if not set(types) <= {t.value for t in CLAIMABLE_JOB_TYPES}:
            raise ValueError("only 'pending' and 'reallocate' jobs can be claimed")
        async with self._sessions() as db:
            row = (await db.execute(text(f"""
                WITH next AS (
                    SELECT incident_id, pipeline_state AS job_type FROM incidents
                    WHERE pipeline_state = ANY(:types)
                    ORDER BY {_SEVERITY_RANK}, received_at, incident_id
                    FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE incidents i
                SET pipeline_state = 'processing', pipeline_attempts = i.pipeline_attempts + 1, pipeline_updated_at = now()
                FROM next WHERE i.incident_id = next.incident_id
                RETURNING i.incident_id, next.job_type, i.pipeline_attempts, i.channel, i.received_at, i.original_text,
                          i.audio_ref, i.location_text, ST_Y(i.caller_gps) AS gps_lat, ST_X(i.caller_gps) AS gps_lon,
                          i.caller_id, i.settings_snapshot
            """), {"types": types})).mappings().first()
            await db.commit()
        if row is None:
            return None
        gps = GeoPoint(lat=row["gps_lat"], lon=row["gps_lon"]) if row["gps_lat"] is not None else None
        return PipelineJob(incident_id=row["incident_id"], job_type=row["job_type"], attempts=row["pipeline_attempts"],
                           channel=row["channel"], received_at=row["received_at"], original_text=row["original_text"],
                           audio_ref=row["audio_ref"], location_text=row["location_text"], caller_gps=gps,
                           caller_id=row["caller_id"], settings_snapshot=row["settings_snapshot"] or {})

    async def requeue_stale_jobs(self, older_than_minutes: int = 10, max_attempts: int = 3) -> tuple[int, int]:
        """Crash recovery: a job stuck in ``processing`` goes back to ``pending``; after ``max_attempts``
        it is marked failed (``ai_failed``) so the dispatcher handles it by hand. Returns (requeued, failed)."""
        async with self._sessions() as db:
            stale = (await db.execute(text(
                "SELECT incident_id, pipeline_attempts FROM incidents WHERE pipeline_state = 'processing' "
                "AND pipeline_updated_at < now() - make_interval(mins => :m) FOR UPDATE SKIP LOCKED"
            ), {"m": older_than_minutes})).all()
            requeued = [i for i, attempts in stale if attempts < max_attempts]
            failed = [i for i, attempts in stale if attempts >= max_attempts]
            if requeued:
                await db.execute(text("UPDATE incidents SET pipeline_state = 'pending', pipeline_updated_at = now() "
                                      "WHERE incident_id = ANY(:ids)"), {"ids": requeued})
            await db.commit()
        for incident_id in failed:
            await self.mark_stage_failed(incident_id, PipelineStage.TRIAGE,
                                         f"worker did not finish after {max_attempts} attempts")
        return len(requeued), len(failed)

    # ------------------------------------------------------------------ stage results
    async def save_transcript(self, incident_id: int, transcript: str, transcript_unclear: bool) -> None:
        async with self._sessions() as db:
            await db.execute(text("UPDATE incidents SET original_text = :t WHERE incident_id = :i AND original_text IS NULL"),
                             {"t": transcript, "i": incident_id})
            await self._merge_ai_details(db, incident_id, "transcript_unclear", transcript_unclear)
            added = await self._reasons(db, incident_id, add=["transcript_unclear"] if transcript_unclear else [])
            await record(db, AuditAction.AI_TRANSCRIPT, incident_id=incident_id,
                         details={"length": len(transcript), "transcript_unclear": transcript_unclear})
            await self._updated(db, incident_id, added)
            await db.commit()

    async def save_location(self, incident_id: int, result: GeocodeResult) -> None:
        result = GeocodeResult.model_validate(_jsonable(result))
        async with self._sessions() as db:
            if result.lat is not None:
                source = "gps" if result.source.value == "gps" else "text"
                await db.execute(text(
                    "UPDATE incidents SET location = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), location_source = :s "
                    "WHERE incident_id = :i"), {"lon": result.lon, "lat": result.lat, "s": source, "i": incident_id})
                added = await self._reasons(db, incident_id, remove=["location_unknown"])
            else:
                await db.execute(text("UPDATE incidents SET location_source = 'unknown' WHERE incident_id = :i AND location IS NULL"),
                                 {"i": incident_id})
                added = await self._reasons(db, incident_id, add=["location_unknown"])
            await self._merge_ai_details(db, incident_id, "geocode", _jsonable(result))
            await record(db, AuditAction.AI_GEOCODE, incident_id=incident_id, details=_jsonable(result))
            await self._updated(db, incident_id, added)
            await db.commit()

    async def save_triage(self, incident_id: int, result: TriageResult) -> None:
        """Store the triage fields. Review reasons (SRS UC-02): ``low_confidence`` below the incident's own
        ``triage_min_confidence`` (settings snapshot), ``missing_info`` when the type is unknown or fields
        are missing. Low confidence never lowers trust or marks a report fake (D-012)."""
        result = TriageResult.model_validate(_jsonable(result))
        async with self._sessions() as db:
            snapshot = await db.scalar(text("SELECT settings_snapshot FROM incidents WHERE incident_id = :i"), {"i": incident_id})
            threshold = (snapshot or {}).get("triage_min_confidence", REGISTRY["triage_min_confidence"].default) / 100
            reasons = []
            if result.overall_confidence < threshold:
                reasons.append("low_confidence")
            if result.incident_type is None or result.missing_fields:
                reasons.append("missing_info")
            if result.transcript_unclear:
                reasons.append("transcript_unclear")
            await db.execute(text(
                "UPDATE incidents SET language = :lang, incident_type = :t, severity = :sev, victims_estimate = :v, "
                "confidence = :c WHERE incident_id = :i"
            ), {"lang": result.language, "t": result.incident_type, "sev": result.severity, "v": result.victims_estimate,
                "c": round(result.overall_confidence, 3), "i": incident_id})
            await self._merge_ai_details(db, incident_id, "triage", _jsonable(result))
            added = await self._reasons(db, incident_id, add=reasons, remove=[r for r in ("low_confidence", "missing_info") if r not in reasons])
            await self._refresh_status(db, incident_id)
            await record(db, AuditAction.AI_TRIAGE, incident_id=incident_id, details=_jsonable(result))
            await self._updated(db, incident_id, added)
            await db.commit()

    async def save_trust(self, incident_id: int, assessment: TrustAssessment) -> None:
        """``review_queue`` → reason ``low_trust`` (needs_check); ``urgent_with_warning`` → warning
        ``low_trust_urgent`` only, the report is never held back (safety rule 3)."""
        assessment = TrustAssessment.model_validate(_jsonable(assessment))
        add = {"review_queue": ["low_trust"], "urgent_with_warning": ["low_trust_urgent"]}.get(assessment.action.value, [])
        async with self._sessions() as db:
            await db.execute(text(
                "UPDATE incidents SET trust_score = :s, trust_tier = :t, trust_signals = CAST(:sig AS jsonb) WHERE incident_id = :i"
            ), {"s": assessment.score, "t": assessment.tier.value,
                "sig": json.dumps([_jsonable(x) for x in assessment.signals]), "i": incident_id})
            await self._merge_ai_details(db, incident_id, "trust_action", assessment.action.value)
            added = await self._reasons(db, incident_id, add=add,
                                        remove=[r for r in ("low_trust", "low_trust_urgent") if r not in add])
            await self._refresh_status(db, incident_id)
            await record(db, AuditAction.AI_TRUST, incident_id=incident_id, details=_jsonable(assessment))
            await self._updated(db, incident_id, added)
            await db.commit()

    # ------------------------------------------------------------------ reads for the agents
    _CANDIDATES = """
        FROM incidents me JOIN incidents c ON c.incident_id <> me.incident_id
         AND c.incident_type = me.incident_type
         AND c.status NOT IN ('closed', 'fake')
         AND c.location IS NOT NULL
         AND ST_DWithin(c.location::geography, me.location::geography, :d)
         AND abs(extract(epoch FROM c.received_at - me.received_at)) <= :w * 60
        WHERE me.incident_id = :i AND me.location IS NOT NULL AND me.incident_type IS NOT NULL
    """

    async def find_duplicate_candidates(self, incident_id: int, distance_m: int, window_min: int) -> list[CandidateRow]:
        async with self._sessions() as db:
            rows = (await db.execute(text(
                "SELECT c.incident_id, c.incident_type, c.received_at, ST_Y(c.location) AS lat, ST_X(c.location) AS lon, "
                "c.original_text, c.caller_id " + self._CANDIDATES +
                " ORDER BY ST_Distance(c.location::geography, me.location::geography), c.received_at"
            ), {"i": incident_id, "d": distance_m, "w": window_min})).mappings().all()
        return [CandidateRow(**dict(r)) for r in rows]

    async def count_independent_nearby(self, incident_id: int, distance_m: int, window_min: int) -> int:
        """Distinct other callers with a report of the same type nearby (D-012). Anonymous reports
        (no caller) are not counted, because their independence cannot be shown."""
        async with self._sessions() as db:
            return int(await db.scalar(text(
                "SELECT count(DISTINCT c.caller_id) " + self._CANDIDATES +
                " AND c.caller_id IS NOT NULL AND c.caller_id IS DISTINCT FROM me.caller_id"
            ), {"i": incident_id, "d": distance_m, "w": window_min}))

    async def get_caller_history(self, caller_id: int) -> CallerHistory | None:
        async with self._sessions() as db:
            row = (await db.execute(text(
                "SELECT caller_id, real_count, fake_count, flagged_until FROM callers WHERE caller_id = :c"
            ), {"c": caller_id})).mappings().first()
        return None if row is None else CallerHistory(**dict(row))

    async def list_available_vehicles(self, types: frozenset[VehicleType]) -> list[VehicleRow]:
        """Status available, no open assignment, driver active and on duty, GPS seen within ``signal_lost_s``.
        Read only: never locks (vehicles are locked only at dispatcher approval)."""
        async with self._sessions() as db:
            lost_s = await get_value(db, "signal_lost_s")
            rows = (await db.execute(text("""
                SELECT v.vehicle_id, v.vehicle_type, ST_Y(v.last_location) AS lat, ST_X(v.last_location) AS lon,
                       v.patient_capacity, v.station_name
                FROM vehicles v JOIN users u ON u.user_id = v.driver_id
                WHERE v.status = 'available' AND v.vehicle_type = ANY(:types) AND v.last_location IS NOT NULL
                  AND u.is_active AND u.on_duty AND v.last_seen_at >= now() - make_interval(secs => :lost)
                  AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.vehicle_id = v.vehicle_id AND a.status = ANY(:open))
                ORDER BY v.vehicle_id
            """), {"types": sorted(VehicleType(t).value for t in types), "lost": lost_s, "open": _OPEN_ASSIGNMENTS})).mappings().all()
        return [VehicleRow(**dict(r)) for r in rows]

    # ------------------------------------------------------------------ duplicates and allocation
    async def save_duplicate_results(self, incident_id: int, results: list[DuplicateCandidateResult]) -> None:
        """Upsert matches. A dispatcher's confirmed/rejected decision is never overwritten. ``auto_linked``
        puts both incidents in one incident group; linking never hides or closes an incident (safety rule 4)."""
        results = [DuplicateCandidateResult.model_validate(_jsonable(r)) for r in results]
        async with self._sessions() as db:
            for r in results:
                await db.execute(text("""
                    INSERT INTO duplicate_candidates (incident_id, candidate_incident_id, match_confidence, distance_m,
                                                      time_diff_s, similarity, decision)
                    VALUES (:i, :c, :m, :d, :t, :s, :dec)
                    ON CONFLICT (incident_id, candidate_incident_id) DO UPDATE SET
                        match_confidence = EXCLUDED.match_confidence, distance_m = EXCLUDED.distance_m,
                        time_diff_s = EXCLUDED.time_diff_s, similarity = EXCLUDED.similarity, decision = EXCLUDED.decision
                    WHERE duplicate_candidates.decision IN ('auto_linked', 'possible', 'separate')
                """), {"i": incident_id, "c": r.candidate_incident_id, "m": r.match_confidence, "d": r.distance_m,
                       "t": r.time_diff_s, "s": round(r.s_meaning, 3), "dec": r.decision.value})
                if r.decision.value == "auto_linked":
                    await self._link(db, incident_id, r.candidate_incident_id)
            possible = [r for r in results if r.decision.value == "possible"]
            added = await self._reasons(db, incident_id, add=["possible_duplicate"] if possible else [])
            await record(db, AuditAction.AI_DUPLICATES, incident_id=incident_id,
                         details={"results": [_jsonable(r) for r in results]})
            await self._updated(db, incident_id, added)
            if possible:
                await self._notify(db, EventName.DUPLICATE_CANDIDATE, incident_id)
            await db.commit()

    @staticmethod
    async def _link(db: AsyncSession, incident_id: int, candidate_id: int) -> None:
        groups = dict((await db.execute(text("SELECT incident_id, group_id FROM incidents WHERE incident_id = ANY(:ids)"),
                                        {"ids": [incident_id, candidate_id]})).all())
        group_id = groups.get(candidate_id) or groups.get(incident_id)
        if group_id is None:
            group_id = await db.scalar(text("INSERT INTO incident_groups DEFAULT VALUES RETURNING group_id"))
        await db.execute(text("UPDATE incidents SET group_id = :g WHERE incident_id = ANY(:ids)"),
                         {"g": group_id, "ids": [incident_id, candidate_id]})
        await db.execute(text("UPDATE incident_groups SET report_count = (SELECT count(*) FROM incidents WHERE group_id = :g) "
                              "WHERE group_id = :g"), {"g": group_id})

    async def save_recommendations(self, incident_id: int, result: AllocationResult) -> None:
        """A new recommendation round: ``batch_no`` + 1, older rounds ``is_current = false``. Never locks."""
        result = AllocationResult.model_validate(_jsonable(result))
        async with self._sessions() as db:
            batch = int(await db.scalar(text("SELECT coalesce(max(batch_no), 0) + 1 FROM recommendations WHERE incident_id = :i"),
                                        {"i": incident_id}))
            await db.execute(text("UPDATE recommendations SET is_current = false WHERE incident_id = :i"), {"i": incident_id})
            for r in result.recommendations:
                await db.execute(text("""
                    INSERT INTO recommendations (incident_id, vehicle_id, rank, eta_seconds, distance_meters, vehicle_type,
                                                 eta_is_approximate, is_spare, route_geometry, batch_no, is_current)
                    VALUES (:i, :v, :rank, :eta, :dist, :type, :approx, :spare, :geom, :batch, true)
                """), {"i": incident_id, "v": r.vehicle_id, "rank": r.rank, "eta": r.eta_seconds, "dist": r.distance_meters,
                       "type": r.vehicle_type.value, "approx": r.eta_is_approximate, "spare": r.is_spare,
                       "geom": r.route_geometry, "batch": batch})
            summary = _jsonable(result)
            summary.pop("recommendations")
            await db.execute(text("UPDATE incidents SET allocation_summary = CAST(:s AS jsonb) WHERE incident_id = :i"),
                             {"s": json.dumps({**summary, "batch_no": batch}), "i": incident_id})
            added = await self._reasons(db, incident_id, add=["vehicle_shortage"] if result.shortage else [],
                                        remove=[] if result.shortage else ["vehicle_shortage"])
            await record(db, AuditAction.AI_ALLOCATION, incident_id=incident_id, details={**_jsonable(result), "batch_no": batch})
            await self._updated(db, incident_id, added)
            await self._notify(db, EventName.RECOMMENDATION_READY, incident_id)
            await db.commit()

    # ------------------------------------------------------------------ end of a job
    async def mark_stage_failed(self, incident_id: int, stage: PipelineStage, error: str) -> None:
        """Manual mode (safety rule 7): the report is kept, gets ``ai_failed`` and goes to ``needs_check``."""
        async with self._sessions() as db:
            await db.execute(text("UPDATE incidents SET pipeline_state = 'failed', pipeline_error = :e, pipeline_updated_at = now() "
                                  "WHERE incident_id = :i"), {"e": f"{PipelineStage(stage).value}: {error}"[:2000], "i": incident_id})
            await self._reasons(db, incident_id, add=["ai_failed"])
            await self._refresh_status(db, incident_id)
            await record(db, AuditAction.AI_FAILED, incident_id=incident_id,
                         details={"stage": PipelineStage(stage).value, "error": error[:500]})
            await self._notify(db, EventName.INCIDENT_AI_FAILED, incident_id)
            await self._notify(db, EventName.REVIEW_ITEM_ADDED, incident_id)
            await db.commit()
        logger.warning("incident %s: AI stage %s failed: %s", incident_id, stage, error)

    async def mark_done(self, incident_id: int) -> None:
        async with self._sessions() as db:
            await db.execute(text("UPDATE incidents SET pipeline_state = 'done', pipeline_error = NULL, pipeline_updated_at = now() "
                                  "WHERE incident_id = :i"), {"i": incident_id})
            await self._notify(db, EventName.INCIDENT_UPDATED, incident_id)
            await db.commit()

    async def heartbeat(self, worker_id: str, info: dict[str, Any]) -> None:
        async with self._sessions() as db:
            await db.execute(text(
                "INSERT INTO worker_heartbeats (worker_id, last_seen_at, info) VALUES (:w, now(), CAST(:info AS jsonb)) "
                "ON CONFLICT (worker_id) DO UPDATE SET last_seen_at = now(), info = EXCLUDED.info"
            ), {"w": worker_id, "info": json.dumps(info)})
            await db.commit()
