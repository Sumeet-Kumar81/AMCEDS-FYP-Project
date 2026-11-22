"""Dispatcher incident queue and detail (B1-A1-20; SRS UC-06 1, UC-02 1a/2a/4a, NFR-S2; SDS §7.2).

Read-only: nothing here writes, locks a vehicle or changes a status. Shapes are contract C-1
(``IncidentSummaryOut``, ``IncidentDetailOut``).

Queue order: critical, high, severity not known yet, medium, low (an unknown severity may still be
critical, the same rule the AI worker uses when it picks jobs); within one severity the report that
has waited longest comes first.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, DuplicateCandidate, Incident, Recommendation, Vehicle
from app.schemas.enums import IncidentStatus, LocationSource, Severity
from app.schemas.incident import (
    AssignmentOut,
    DispatcherDecisionOut,
    DuplicateCandidateOut,
    IncidentDetailOut,
    IncidentSummaryOut,
    LocationOut,
    RecommendationOut,
    TrustSignalOut,
)

#: Statuses shown in the queue unless closed ones are asked for.
OPEN_STATUSES: frozenset[IncidentStatus] = frozenset({
    IncidentStatus.NEW, IncidentStatus.TRIAGED, IncidentStatus.NEEDS_CHECK,
    IncidentStatus.DISPATCHED, IncidentStatus.ON_SCENE,
})
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

SEVERITY_RANK = case(
    (Incident.severity == Severity.CRITICAL.value, 0),
    (Incident.severity == Severity.HIGH.value, 1),
    (Incident.severity.is_(None), 2),
    (Incident.severity == Severity.MEDIUM.value, 3),
    (Incident.severity == Severity.LOW.value, 4),
    else_=5,
)


def _columns() -> tuple[Any, ...]:
    return (Incident, func.ST_Y(Incident.location).label("lat"), func.ST_X(Incident.location).label("lon"))


def _location(row: Incident, lat: float | None, lon: float | None) -> LocationOut:
    """C-1 location. A record that does not satisfy its own source rule is shown as what it really has."""
    text_words = (row.location_text or "").strip() or None
    has_point = lat is not None and lon is not None
    source = LocationSource(row.location_source)
    if source is LocationSource.GPS and not has_point:
        source = LocationSource.TEXT if text_words else LocationSource.UNKNOWN
    if source is LocationSource.TEXT and not text_words:
        source = LocationSource.GPS if has_point else LocationSource.UNKNOWN
    return LocationOut(lat=lat if has_point else None, lon=lon if has_point else None, text=text_words, source=source)


def _summary_fields(row: Incident, lat: float | None, lon: float | None) -> dict[str, Any]:
    return {
        "incident_id": row.incident_id,
        "reference_no": row.reference_no,
        "channel": row.channel,
        "received_at": row.received_at,
        "language": row.language,
        "location": _location(row, lat, lon),
        "incident_type": row.incident_type,
        "severity": row.severity,
        "victims_estimate": row.victims_estimate,
        "confidence": float(row.confidence) if row.confidence is not None else None,
        "trust_score": row.trust_score,
        "trust_tier": row.trust_tier,
        "group_id": row.group_id,
        "status": row.status,
        "review_reasons": list(row.review_reasons or []),
    }


def queue_query(statuses: Sequence[IncidentStatus] | None, severities: Sequence[Severity | None] | None,
                include_closed: bool) -> Select[Any]:
    query = select(*_columns())
    wanted = set(statuses) if statuses else (None if include_closed else set(OPEN_STATUSES))
    if wanted is not None:
        query = query.where(Incident.status.in_(sorted(s.value for s in wanted)))
    if severities:
        named = sorted(s.value for s in severities if s is not None)
        cond = Incident.severity.in_(named) if named else None
        if None in severities:
            cond = Incident.severity.is_(None) if cond is None else (cond | Incident.severity.is_(None))
        query = query.where(cond)
    return query.order_by(SEVERITY_RANK, Incident.received_at, Incident.incident_id)


async def list_incidents(db: AsyncSession, *, statuses: Sequence[IncidentStatus] | None = None,
                         severities: Sequence[Severity | None] | None = None, include_closed: bool = False,
                         limit: int = DEFAULT_LIMIT, offset: int = 0) -> list[IncidentSummaryOut]:
    rows = (await db.execute(queue_query(statuses, severities, include_closed).limit(limit).offset(offset))).all()
    return [IncidentSummaryOut(**_summary_fields(r.Incident, r.lat, r.lon)) for r in rows]


async def get_incident(db: AsyncSession, incident_id: int) -> IncidentDetailOut | None:
    found = (await db.execute(select(*_columns()).where(Incident.incident_id == incident_id))).first()
    if found is None:
        return None
    row: Incident = found.Incident

    recs = (await db.execute(
        select(Recommendation, Vehicle.plate_number)
        .join(Vehicle, Vehicle.vehicle_id == Recommendation.vehicle_id)
        .where(Recommendation.incident_id == incident_id, Recommendation.is_current.is_(True))
        .order_by(Recommendation.rank, Recommendation.rec_id)
    )).all()
    duplicates = (await db.scalars(
        select(DuplicateCandidate).where(DuplicateCandidate.incident_id == incident_id)
        .order_by(DuplicateCandidate.match_confidence.desc(), DuplicateCandidate.duplicate_id)
    )).all()
    assignments = (await db.scalars(
        select(Assignment).where(Assignment.incident_id == incident_id).order_by(Assignment.approved_at, Assignment.assignment_id)
    )).all()

    first = assignments[0] if assignments else None
    return IncidentDetailOut(
        **_summary_fields(row, found.lat, found.lon),
        original_text=row.original_text,
        audio_ref=row.audio_ref,
        reporter_name=row.reporter_name,
        ai_details=row.ai_details,
        trust_signals=[TrustSignalOut(code=s["code"], points=s["points"], detail=s.get("detail"))
                       for s in (row.trust_signals or [])],
        allocation_summary=row.allocation_summary,
        duplicate_candidates=[DuplicateCandidateOut(
            duplicate_id=d.duplicate_id, candidate_incident_id=d.candidate_incident_id,
            match_confidence=d.match_confidence, distance_m=d.distance_m, time_diff_s=d.time_diff_s,
            similarity=float(d.similarity) if d.similarity is not None else None, decision=d.decision,
            decided_by=d.decided_by, decided_at=d.decided_at) for d in duplicates],
        recommendations=[RecommendationOut(
            rec_id=r.rec_id, vehicle_id=r.vehicle_id, rank=r.rank, eta_seconds=r.eta_seconds,
            distance_meters=r.distance_meters, created_at=r.created_at, vehicle_type=r.vehicle_type,
            eta_is_approximate=r.eta_is_approximate, is_spare=r.is_spare, route_geometry=r.route_geometry,
            batch_no=r.batch_no, is_current=r.is_current, plate_number=plate) for r, plate in recs],
        assignments=[AssignmentOut(
            assignment_id=a.assignment_id, vehicle_id=a.vehicle_id, approved_by=a.approved_by,
            hospital_id=a.hospital_id, status=a.status, approved_at=a.approved_at, accepted_at=a.accepted_at,
            on_scene_at=a.on_scene_at, picked_up_at=a.picked_up_at, at_hospital_at=a.at_hospital_at,
            completed_at=a.completed_at, notified_at=a.notified_at, decline_reason=a.decline_reason,
            declined_at=a.declined_at, timed_out_at=a.timed_out_at) for a in assignments],
        dispatcher_decision=(DispatcherDecisionOut(approved_by=first.approved_by, approved_at=first.approved_at)
                             if first else None),
    )
