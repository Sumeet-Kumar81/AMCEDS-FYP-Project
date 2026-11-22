"""Assignment lifecycle — from approval until the vehicle is free again (B1-A1-26; SRS UC-08 2/2a, UC-09
1–4, 1a, 2a; SDS Table 5.8, §3.2 steps 8–16; TC-27, TC-29 API part, TC-48; contract C-7).

Every change runs in one transaction and locks in the same order as dispatch approval (incident,
vehicle, assignment) so the two never deadlock. Allowed moves come only from C-7
(``check_assignment_transition``, ``next_vehicle_status``); anything else is 409 and changes nothing.
Each change writes its timestamp and an audit row; freeing a vehicle also writes ``vehicle.unlocked``.

Incident status follows its vehicles: first arrival → ``on_scene``; when no open assignment is left and
at least one finished the trip → ``closed``; when no open assignment is left and none finished (all
declined or cancelled) → ``needs_check`` with a review reason, so the dispatcher sends another vehicle
(urgent reports are never silently dropped). Driver alerts are still not sent (B1-A1-30).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, Hospital, Incident, Recommendation, User, Vehicle
from app.schemas.assignment import (
    OPEN_ASSIGNMENT_STATUSES,
    VEHICLE_STATUS_FOR_ASSIGNMENT,
    DeclineReason,
    DriverAssignmentOut,
    HospitalOut,
    InvalidTransition,
    TripStatus,
    check_assignment_transition,
    next_vehicle_status,
)
from app.schemas.enums import AssignmentStatus, IncidentStatus, VehicleStatus
from app.schemas.incident import LocationOut
from app.services.audit import AuditAction, record

log = logging.getLogger(__name__)
OPEN = sorted(s.value for s in OPEN_ASSIGNMENT_STATUSES)
ACTIVE_INCIDENT = frozenset({IncidentStatus.DISPATCHED.value, IncidentStatus.ON_SCENE.value})

#: review reasons set when the last vehicle of an incident did not finish the trip
REASON_DECLINED = "vehicle_declined"
REASON_CANCELLED = "vehicle_cancelled"


class AssignmentError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _lock(db: AsyncSession, assignment_id: int) -> tuple[Assignment, Vehicle, Incident]:
    ids = (await db.execute(select(Assignment.incident_id, Assignment.vehicle_id)
                            .where(Assignment.assignment_id == assignment_id))).first()
    if ids is None:
        raise AssignmentError(404, "not_found", "No such assignment.")
    incident = await db.scalar(select(Incident).where(Incident.incident_id == ids.incident_id).with_for_update())
    vehicle = await db.scalar(select(Vehicle).where(Vehicle.vehicle_id == ids.vehicle_id).with_for_update())
    assignment = await db.scalar(select(Assignment).where(Assignment.assignment_id == assignment_id).with_for_update())
    assert incident is not None and vehicle is not None and assignment is not None
    return assignment, vehicle, incident


def _move(assignment: Assignment, new: AssignmentStatus) -> None:
    try:
        check_assignment_transition(AssignmentStatus(assignment.status), new)
    except InvalidTransition as exc:
        raise AssignmentError(409, "invalid_transition", str(exc), {"status": assignment.status, "to": new.value}) from None
    assignment.status = new.value


async def _settle_incident(db: AsyncSession, incident: Incident, reason_if_none_finished: str) -> dict[str, str] | None:
    """After a vehicle left the incident: close it, or send it back to the dispatcher. Returns the change."""
    await db.flush()
    rows = (await db.execute(select(Assignment.status, func.count()).where(Assignment.incident_id == incident.incident_id)
                             .group_by(Assignment.status))).all()
    counts = {status: n for status, n in rows}
    if any(counts.get(s, 0) for s in OPEN) or incident.status not in ACTIVE_INCIDENT:
        return None
    before = incident.status
    if counts.get(AssignmentStatus.COMPLETED.value, 0):
        incident.status = IncidentStatus.CLOSED.value
    else:
        incident.status = IncidentStatus.NEEDS_CHECK.value
        incident.review_reasons = sorted(set(incident.review_reasons or []) | {reason_if_none_finished})
    return {"from": before, "to": incident.status}


async def _free(db: AsyncSession, vehicle: Vehicle, assignment: Assignment, user_id: int, why: str) -> None:
    vehicle.status = VehicleStatus.AVAILABLE.value
    await record(db, AuditAction.VEHICLE_UNLOCKED, user_id=user_id, incident_id=assignment.incident_id,
                 details={"vehicle_id": vehicle.vehicle_id, "assignment_id": assignment.assignment_id, "why": why})


# ---------------------------------------------------------------- driver
async def accept(db: AsyncSession, assignment_id: int, driver: User) -> Assignment:
    assignment, vehicle, incident = await _lock(db, assignment_id)
    if not driver.on_duty:
        raise AssignmentError(409, "driver_off_duty", "Start duty before accepting an assignment.")
    _move(assignment, AssignmentStatus.ACCEPTED)
    assignment.accepted_at = _now()
    vehicle.status = VEHICLE_STATUS_FOR_ASSIGNMENT[AssignmentStatus.ACCEPTED].value  # en_route
    await record(db, AuditAction.ASSIGNMENT_ACCEPTED, user_id=driver.user_id, incident_id=incident.incident_id,
                 details={"assignment_id": assignment.assignment_id, "vehicle_id": vehicle.vehicle_id})
    return assignment


async def decline(db: AsyncSession, assignment_id: int, driver: User, reason: DeclineReason) -> Assignment:
    assignment, vehicle, incident = await _lock(db, assignment_id)
    _move(assignment, AssignmentStatus.DECLINED)
    assignment.declined_at = _now()
    assignment.decline_reason = reason.value
    await _free(db, vehicle, assignment, driver.user_id, "declined")
    change = await _settle_incident(db, incident, REASON_DECLINED)
    await record(db, AuditAction.ASSIGNMENT_DECLINED, user_id=driver.user_id, incident_id=incident.incident_id,
                 details={"assignment_id": assignment.assignment_id, "vehicle_id": vehicle.vehicle_id,
                          "reason": reason.value, "incident_status": change})
    return assignment


async def trip_status(db: AsyncSession, assignment_id: int, driver: User, step: TripStatus) -> Assignment:
    assignment, vehicle, incident = await _lock(db, assignment_id)
    if assignment.status != AssignmentStatus.ACCEPTED.value:
        raise AssignmentError(409, "invalid_transition", f"Trip steps need an accepted assignment (it is '{assignment.status}').",
                              {"status": assignment.status, "step": step.value})
    try:
        new_vehicle = next_vehicle_status(VehicleStatus(vehicle.status), step)
    except InvalidTransition as exc:
        raise AssignmentError(409, "invalid_transition", str(exc), {"vehicle_status": vehicle.status, "step": step.value}) from None
    now, change = _now(), None
    before_vehicle = vehicle.status
    if step is TripStatus.ON_SCENE:
        assignment.on_scene_at = now
        if incident.status == IncidentStatus.DISPATCHED.value:
            change = {"from": incident.status, "to": IncidentStatus.ON_SCENE.value}
            incident.status = IncidentStatus.ON_SCENE.value
    elif step is TripStatus.PICKED_UP:
        assignment.picked_up_at = now
    elif step is TripStatus.AT_HOSPITAL:
        assignment.at_hospital_at = now
    vehicle.status = new_vehicle.value
    if step is TripStatus.AVAILABLE:
        _move(assignment, AssignmentStatus.COMPLETED)
        assignment.completed_at = now
        await _free(db, vehicle, assignment, driver.user_id, "trip completed")
        change = await _settle_incident(db, incident, REASON_CANCELLED)
    await record(db, AuditAction.ASSIGNMENT_STATUS_CHANGED, user_id=driver.user_id, incident_id=incident.incident_id,
                 details={"assignment_id": assignment.assignment_id, "vehicle_id": vehicle.vehicle_id, "step": step.value,
                          "vehicle_status": {"from": before_vehicle, "to": vehicle.status}, "incident_status": change})
    return assignment


async def current(db: AsyncSession, driver: User) -> DriverAssignmentOut | None:
    """The driver's open assignment (the vehicle they drive), as the driver app shows it."""
    row = (await db.execute(
        select(Assignment, Incident, func.ST_Y(Incident.location).label("lat"), func.ST_X(Incident.location).label("lon"))
        .join(Vehicle, Vehicle.vehicle_id == Assignment.vehicle_id)
        .join(Incident, Incident.incident_id == Assignment.incident_id)
        .where(Vehicle.driver_id == driver.user_id, Assignment.status.in_(OPEN))
        .order_by(Assignment.approved_at.desc())
    )).first()
    if row is None:
        return None
    a, inc = row.Assignment, row.Incident
    rec = await db.scalar(select(Recommendation).where(Recommendation.incident_id == inc.incident_id,
                                                       Recommendation.vehicle_id == a.vehicle_id,
                                                       Recommendation.is_current.is_(True)))
    has_point = row.lat is not None and row.lon is not None
    words = (inc.location_text or "").strip() or None
    source = "gps" if has_point and inc.location_source == "gps" else ("text" if words else ("gps" if has_point else "unknown"))
    hospital = None
    if a.hospital_id is not None:
        h = (await db.execute(select(Hospital, func.ST_Y(Hospital.location).label("lat"), func.ST_X(Hospital.location).label("lon"))
                              .where(Hospital.hospital_id == a.hospital_id))).first()
        if h is not None:
            hospital = HospitalOut(hospital_id=h.Hospital.hospital_id, name=h.Hospital.name, lat=h.lat, lon=h.lon)
    return DriverAssignmentOut(
        assignment_id=a.assignment_id, incident_id=inc.incident_id, reference_no=inc.reference_no, status=a.status,
        incident_type=inc.incident_type, severity=inc.severity,
        location=LocationOut(lat=row.lat if has_point else None, lon=row.lon if has_point else None, text=words, source=source),
        patients=inc.victims_estimate, eta_seconds=rec.eta_seconds if rec else None,
        eta_is_approximate=rec.eta_is_approximate if rec else True, hospital=hospital,
        notified_at=a.notified_at, respond_by=None,
    )


# ---------------------------------------------------------------- dispatcher
async def cancel(db: AsyncSession, assignment_id: int, dispatcher: User, reason: str | None) -> Assignment:
    assignment, vehicle, incident = await _lock(db, assignment_id)
    _move(assignment, AssignmentStatus.CANCELLED)
    await _free(db, vehicle, assignment, dispatcher.user_id, "cancelled by the dispatcher")
    change = await _settle_incident(db, incident, REASON_CANCELLED)
    await record(db, AuditAction.ASSIGNMENT_CANCELLED, user_id=dispatcher.user_id, incident_id=incident.incident_id,
                 details={"assignment_id": assignment.assignment_id, "vehicle_id": vehicle.vehicle_id, "reason": reason,
                          "incident_status": change})
    return assignment


async def change_hospital(db: AsyncSession, assignment_id: int, dispatcher: User, hospital_id: int) -> Assignment:
    assignment, _vehicle, incident = await _lock(db, assignment_id)
    if assignment.status not in OPEN:
        raise AssignmentError(409, "invalid_transition", f"The assignment is '{assignment.status}'; its hospital cannot change.",
                              {"status": assignment.status})
    hospital = await db.get(Hospital, hospital_id)
    if hospital is None or not hospital.is_active:
        raise AssignmentError(404, "not_found", "No such active hospital.", {"hospital_id": hospital_id})
    before = assignment.hospital_id
    assignment.hospital_id = hospital_id
    await record(db, AuditAction.ASSIGNMENT_HOSPITAL_CHANGED, user_id=dispatcher.user_id, incident_id=incident.incident_id,
                 details={"assignment_id": assignment.assignment_id, "from": before, "to": hospital_id,
                          "driver_alert": "not sent: notification service not built yet (B1-A1-30)"})
    return assignment


async def hospitals(db: AsyncSession) -> list[HospitalOut]:
    rows = (await db.execute(select(Hospital, func.ST_Y(Hospital.location).label("lat"), func.ST_X(Hospital.location).label("lon"))
                             .where(Hospital.is_active).order_by(Hospital.name))).all()
    return [HospitalOut(hospital_id=r.Hospital.hospital_id, name=r.Hospital.name, lat=r.lat, lon=r.lon) for r in rows]
