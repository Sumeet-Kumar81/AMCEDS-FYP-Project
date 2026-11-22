"""Dispatch approval — the only way a vehicle is sent (B1-A1-25; SRS UC-06 3–4, 3a, 4a; NFR-S1, S3, S6,
S9; TC-21, TC-22, TC-46; safety rules 2, 3, 5, 6, 9).

In one transaction: lock the incident, then the chosen vehicles in id order (no deadlocks); refuse a
fake or closed incident; refuse a vehicle that already has an open assignment (``vehicle_locked``) or
cannot take one (``vehicle_unavailable``: status not available, no driver, driver off duty), offering
the next best recommended vehicles; create one ``approved`` assignment per vehicle with the approving
dispatcher and time; vehicle → ``assigned``; incident → ``dispatched``; audit what the AI suggested
next to what the dispatcher chose. The partial unique index ``uq_assignments_open_vehicle`` is the last
guard against two dispatchers taking the same vehicle at the same moment.

Trust, severity and duplicate checks are deliberately not preconditions: an urgent report is never
held back (rule 3) and the dispatcher's decision is a human one. Driver alerts are not sent yet
(notification service B1-A1-30, driver app B1-A3-16).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Hospital, Incident, Recommendation, User, Vehicle
from app.schemas.assignment import OPEN_ASSIGNMENT_STATUSES
from app.schemas.dispatch import DispatchIn, VehicleOut
from app.schemas.enums import AssignmentStatus, IncidentStatus, VehicleStatus, VehicleType
from app.services.audit import AuditAction, record
from app.services.settings import get_value

log = logging.getLogger(__name__)

NOT_DISPATCHABLE = frozenset({IncidentStatus.FAKE.value, IncidentStatus.CLOSED.value})
#: statuses that become ``dispatched``; later statuses (on scene) are kept when a backup is sent
BECOMES_DISPATCHED = frozenset({IncidentStatus.NEW.value, IncidentStatus.TRIAGED.value, IncidentStatus.NEEDS_CHECK.value})
OPEN = sorted(s.value for s in OPEN_ASSIGNMENT_STATUSES)
NEXT_BEST_MAX = 3


class DispatchError(Exception):
    """A refusal with an HTTP status, a contract code and details for the screen."""

    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


@dataclass(frozen=True)
class _Fit:
    vehicle_id: int
    reason: str | None  # None = can take the assignment


def _open_assignment():
    return exists().where(Assignment.vehicle_id == Vehicle.vehicle_id, Assignment.status.in_(OPEN))


async def _fitness(db: AsyncSession, vehicles: list[Vehicle]) -> list[_Fit]:
    ids = [v.vehicle_id for v in vehicles]
    busy = set(await db.scalars(select(Assignment.vehicle_id).where(Assignment.vehicle_id.in_(ids), Assignment.status.in_(OPEN))))
    driver_ids = [v.driver_id for v in vehicles if v.driver_id]
    on_duty = set(await db.scalars(select(User.user_id).where(User.user_id.in_(driver_ids), User.on_duty, User.is_active)))
    fits = []
    for v in vehicles:
        if v.vehicle_id in busy:
            reason = "locked"
        elif v.status != VehicleStatus.AVAILABLE.value:
            reason = f"status_{v.status}"
        elif v.driver_id is None:
            reason = "no_driver"
        elif v.driver_id not in on_duty:
            reason = "driver_off_duty"
        else:
            reason = None
        fits.append(_Fit(v.vehicle_id, reason))
    return fits


async def next_best(db: AsyncSession, incident_id: int, exclude: set[int]) -> list[int]:
    """Current recommendations, in rank order, that could be dispatched right now."""
    rows = (await db.execute(
        select(Recommendation.vehicle_id)
        .join(Vehicle, Vehicle.vehicle_id == Recommendation.vehicle_id)
        .join(User, User.user_id == Vehicle.driver_id)
        .where(Recommendation.incident_id == incident_id, Recommendation.is_current.is_(True),
               Vehicle.status == VehicleStatus.AVAILABLE.value, User.on_duty, User.is_active, ~_open_assignment())
        .order_by(Recommendation.rank, Recommendation.rec_id)
    )).scalars().all()
    seen: list[int] = []
    for vid in rows:
        if vid not in exclude and vid not in seen:
            seen.append(vid)
    return seen[:NEXT_BEST_MAX]


async def approve(db: AsyncSession, incident_id: int, body: DispatchIn, dispatcher: User) -> list[Assignment]:
    """Create the assignments, or raise DispatchError. Flushes; the caller commits."""
    incident = await db.scalar(select(Incident).where(Incident.incident_id == incident_id).with_for_update())
    if incident is None:
        raise DispatchError(404, "not_found", "No such incident.")
    if incident.status in NOT_DISPATCHABLE:
        raise DispatchError(409, "incident_not_dispatchable",
                            f"This incident is {incident.status}; no vehicle can be sent to it.",
                            {"status": incident.status})

    wanted = sorted(body.vehicle_ids)
    vehicles = list((await db.scalars(
        select(Vehicle).where(Vehicle.vehicle_id.in_(wanted)).order_by(Vehicle.vehicle_id).with_for_update()
    )).all())
    missing = sorted(set(wanted) - {v.vehicle_id for v in vehicles})
    if missing:
        raise DispatchError(404, "not_found", "No such vehicle.", {"vehicle_ids": missing})

    if body.hospital_id is not None:
        hospital = await db.get(Hospital, body.hospital_id)
        if hospital is None or not hospital.is_active:
            raise DispatchError(404, "not_found", "No such active hospital.", {"hospital_id": body.hospital_id})

    fits = await _fitness(db, vehicles)
    locked = [f.vehicle_id for f in fits if f.reason == "locked"]
    unfit = [{"vehicle_id": f.vehicle_id, "reason": f.reason} for f in fits if f.reason not in (None, "locked")]
    if locked:
        raise DispatchError(409, "vehicle_locked", "A chosen vehicle already has an open assignment.",
                            {"vehicle_ids": locked, "next_best": await next_best(db, incident_id, set(wanted))})
    if unfit:
        raise DispatchError(409, "vehicle_unavailable", "A chosen vehicle cannot take an assignment now.",
                            {"vehicles": unfit, "next_best": await next_best(db, incident_id, set(wanted))})

    recommended = list((await db.scalars(
        select(Recommendation.vehicle_id).where(Recommendation.incident_id == incident_id, Recommendation.is_current.is_(True))
        .order_by(Recommendation.rank, Recommendation.rec_id)
    )).all())
    lost_s = int(await get_value(db, "signal_lost_s"))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lost_s)
    signal_lost = [v.vehicle_id for v in vehicles if v.last_seen_at is None or v.last_seen_at < cutoff]

    now = datetime.now(timezone.utc)
    assignments = [Assignment(incident_id=incident_id, vehicle_id=v.vehicle_id, approved_by=dispatcher.user_id,
                              hospital_id=body.hospital_id, status=AssignmentStatus.APPROVED.value, approved_at=now)
                   for v in vehicles]
    db.add_all(assignments)
    try:
        await db.flush()  # the partial unique index decides a same-moment race
    except IntegrityError as exc:
        if "uq_assignments_open_vehicle" not in str(exc.orig):
            raise
        raise DispatchError(409, "vehicle_locked", "A chosen vehicle was just taken by another dispatcher.",
                            {"vehicle_ids": wanted, "next_best": [], "race": True}) from None

    previous_status = incident.status
    for v in vehicles:
        v.status = VehicleStatus.ASSIGNED.value
    if incident.status in BECOMES_DISPATCHED:
        incident.status = IncidentStatus.DISPATCHED.value
    await db.flush()

    await record(db, AuditAction.DISPATCH_APPROVED, user_id=dispatcher.user_id, incident_id=incident_id, details={
        "recommended": recommended,
        "selected": wanted,
        "same_as_ai": bool(recommended) and set(wanted) <= set(recommended),
        "override_reason": body.override_reason,
        "manual_mode": not recommended,
        "hospital_id": body.hospital_id,
        "signal_lost": signal_lost,
        "assignment_ids": [a.assignment_id for a in assignments],
        "incident_status": {"from": previous_status, "to": incident.status},
        "driver_alert": "not sent: notification service not built yet (B1-A1-30)",
    })
    for a in assignments:
        await record(db, AuditAction.VEHICLE_LOCKED, user_id=dispatcher.user_id, incident_id=incident_id,
                     details={"vehicle_id": a.vehicle_id, "assignment_id": a.assignment_id})
    log.info("incident %s dispatched by user %s: vehicles %s (AI suggested %s)", incident_id,
             dispatcher.user_id, wanted, recommended)
    return assignments


async def list_vehicles(db: AsyncSession, *, incident_id: int | None = None, types: list[VehicleType] | None = None,
                        available_only: bool = False) -> list[VehicleOut]:
    """All vehicles for the dispatcher; nearest first (straight line) when an incident is given."""
    lost_s = int(await get_value(db, "signal_lost_s"))
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lost_s)
    has_open = _open_assignment().label("has_open")
    cols: list[Any] = [Vehicle, User.full_name, User.on_duty, User.is_active, has_open,
                       func.ST_Y(Vehicle.last_location).label("lat"), func.ST_X(Vehicle.last_location).label("lon")]
    query = select(*cols).outerjoin(User, User.user_id == Vehicle.driver_id)
    distance = None
    if incident_id is not None:
        where = select(Incident.location).where(Incident.incident_id == incident_id).scalar_subquery()
        distance = func.ST_Distance(func.Geography(Vehicle.last_location), func.Geography(where))
        query = query.add_columns(distance.label("distance"))
    if types:
        query = query.where(Vehicle.vehicle_type.in_([t.value for t in types]))

    rows = (await db.execute(query.order_by(Vehicle.vehicle_type, Vehicle.plate_number))).all()
    out: list[VehicleOut] = []
    for r in rows:
        v: Vehicle = r.Vehicle
        on_duty = bool(r.on_duty and r.is_active)
        can = v.status == VehicleStatus.AVAILABLE.value and v.driver_id is not None and on_duty and not r.has_open
        if available_only and not can:
            continue
        dist = getattr(r, "distance", None)
        out.append(VehicleOut(
            vehicle_id=v.vehicle_id, plate_number=v.plate_number, vehicle_type=v.vehicle_type, status=v.status,
            station_name=v.station_name, patient_capacity=v.patient_capacity, driver_id=v.driver_id,
            driver_name=r.full_name, driver_on_duty=on_duty, lat=r.lat, lon=r.lon, last_seen_at=v.last_seen_at,
            signal_lost=v.last_seen_at is None or v.last_seen_at < cutoff, has_open_assignment=bool(r.has_open),
            can_dispatch=can, distance_meters=round(dist) if dist is not None else None,
        ))
    if incident_id is not None:  # dispatchable first, then nearest, unknown distance last
        out.sort(key=lambda x: (not x.can_dispatch, x.distance_meters is None, x.distance_meters or 0, x.plate_number))
    return out
