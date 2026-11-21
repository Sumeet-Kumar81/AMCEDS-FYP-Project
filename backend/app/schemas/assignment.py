"""Contract C-7: what the driver app receives, and which status changes are allowed (task B1-A1-05).

Sources: SRS UC-08 (assignment alert: type, severity, location, patients; accept or Cannot Go within
60 seconds), UC-09 (trip status: on scene -> picked up -> at hospital -> available), SDS v1.1
Tables 5.5 (vehicle statuses), 5.8 (assignments) and 5.9 (hospitals), decision D-005.

Decided by the project developer for C-7 v1:
  * A vehicle may go from ``on_scene`` straight to ``available`` (no patient carried, e.g. a fire truck).
  * The payload carries ``respond_by`` (alert time + the answer limit) so the app can show a countdown.

The transition tables are the single source of truth; the dispatch and tracking services
(B1-A1-25/26/27) must use ``check_assignment_transition`` and ``next_vehicle_status``.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import AssignmentStatus, IncidentType, Severity, VehicleStatus
from app.schemas.incident import REFERENCE_NO_PATTERN, LocationOut

DEFAULT_ANSWER_LIMIT_SECONDS = 60  # SRS Appendix C timer (admin-configurable; the real value comes from settings)


class InvalidTransition(ValueError):
    """A status change that the contract does not allow."""


class TripStatus(StrEnum):
    """What the driver app reports during a trip (SRS UC-09; SDS Table 4.3 ``.../status``)."""

    ON_SCENE = "on_scene"
    PICKED_UP = "picked_up"
    AT_HOSPITAL = "at_hospital"
    AVAILABLE = "available"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HospitalOut(_Contract):
    """A hospital the driver can be sent to (SDS Table 5.9)."""

    hospital_id: int
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DriverAssignmentOut(_Contract):
    """The assignment as the driver app shows it (UC-08 step 1). Sent in ``assignment.new`` / ``.updated``."""

    assignment_id: int
    incident_id: int
    reference_no: str = Field(pattern=REFERENCE_NO_PATTERN)
    status: AssignmentStatus
    incident_type: IncidentType | None  # None when the AI could not tell (manual dispatch)
    severity: Severity | None
    location: LocationOut  # the destination; navigation starts from the vehicle's own position
    patients: int | None = Field(ge=0)  # victims_estimate; None = unknown
    eta_seconds: int | None = Field(ge=0)
    eta_is_approximate: bool  # straight-line ETA must be labelled "approximate" (safety rule)
    hospital: HospitalOut | None = None
    notified_at: AwareDatetime | None = None
    respond_by: AwareDatetime | None = None

    @model_validator(mode="after")
    def _respond_by_follows_the_alert(self) -> DriverAssignmentOut:
        if self.respond_by is not None and (self.notified_at is None or self.respond_by <= self.notified_at):
            raise ValueError("respond_by must be after notified_at")
        return self


# ------------------------------------------------------------------ allowed changes
ASSIGNMENT_TRANSITIONS: dict[AssignmentStatus, frozenset[AssignmentStatus]] = {
    AssignmentStatus.APPROVED: frozenset(
        {AssignmentStatus.ACCEPTED, AssignmentStatus.DECLINED, AssignmentStatus.TIMED_OUT, AssignmentStatus.CANCELLED}
    ),
    AssignmentStatus.ACCEPTED: frozenset({AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED}),
    AssignmentStatus.DECLINED: frozenset(),
    AssignmentStatus.TIMED_OUT: frozenset(),
    AssignmentStatus.COMPLETED: frozenset(),
    AssignmentStatus.CANCELLED: frozenset(),
}
"""Only ``approved`` and ``accepted`` are open (the partial unique index on assignments covers exactly these)."""

OPEN_ASSIGNMENT_STATUSES = frozenset(s for s, nxt in ASSIGNMENT_TRANSITIONS.items() if nxt)

VEHICLE_STATUS_FOR_ASSIGNMENT: dict[AssignmentStatus, VehicleStatus] = {
    AssignmentStatus.APPROVED: VehicleStatus.ASSIGNED,  # locked at approval, never at recommendation
    AssignmentStatus.ACCEPTED: VehicleStatus.EN_ROUTE,  # UC-08 step 3: navigation starts
    AssignmentStatus.DECLINED: VehicleStatus.AVAILABLE,  # UC-08 2a: the vehicle is freed
    AssignmentStatus.TIMED_OUT: VehicleStatus.AVAILABLE,  # UC-08 2b
    AssignmentStatus.CANCELLED: VehicleStatus.AVAILABLE,
    AssignmentStatus.COMPLETED: VehicleStatus.AVAILABLE,  # UC-09 step 4: the vehicle is unlocked
}

TRIP_TRANSITIONS: dict[tuple[VehicleStatus, TripStatus], VehicleStatus] = {
    (VehicleStatus.EN_ROUTE, TripStatus.ON_SCENE): VehicleStatus.ON_SCENE,  # UC-09 1 / 1a
    (VehicleStatus.ON_SCENE, TripStatus.PICKED_UP): VehicleStatus.TRANSPORTING,  # UC-09 2
    (VehicleStatus.TRANSPORTING, TripStatus.AT_HOSPITAL): VehicleStatus.AT_HOSPITAL,  # UC-09 3
    (VehicleStatus.AT_HOSPITAL, TripStatus.AVAILABLE): VehicleStatus.AVAILABLE,  # UC-09 4
    (VehicleStatus.ON_SCENE, TripStatus.AVAILABLE): VehicleStatus.AVAILABLE,  # no patient carried (C-7 v1)
}
"""A trip step ending in ``available`` also completes the assignment (``accepted`` -> ``completed``)."""


def check_assignment_transition(current: AssignmentStatus, new: AssignmentStatus) -> None:
    if new not in ASSIGNMENT_TRANSITIONS[current]:
        raise InvalidTransition(f"assignment cannot go from '{current}' to '{new}'")


def next_vehicle_status(current: VehicleStatus, step: TripStatus) -> VehicleStatus:
    try:
        return TRIP_TRANSITIONS[(current, step)]
    except KeyError:
        raise InvalidTransition(f"trip step '{step}' is not allowed while the vehicle is '{current}'") from None
