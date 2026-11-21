"""Contract C-7 tests (B1-A1-05): the driver payload and the allowed status changes."""
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.assignment import (
    ASSIGNMENT_TRANSITIONS,
    DEFAULT_ANSWER_LIMIT_SECONDS,
    OPEN_ASSIGNMENT_STATUSES,
    TRIP_TRANSITIONS,
    VEHICLE_STATUS_FOR_ASSIGNMENT,
    DriverAssignmentOut,
    InvalidTransition,
    TripStatus,
    check_assignment_transition,
    next_vehicle_status,
)
from app.schemas.enums import AssignmentStatus as A
from app.schemas.enums import VehicleStatus as V

PAYLOAD: dict[str, Any] = {
    "assignment_id": 7, "incident_id": 123, "reference_no": "INC-000123", "status": "approved",
    "incident_type": "accident", "severity": "high",
    "location": {"lat": 27.7052, "lon": 68.8574, "text": "near the market", "source": "gps"},
    "patients": 6, "eta_seconds": 420, "eta_is_approximate": False,
    "hospital": {"hospital_id": 3, "name": "SIMULATED Civil Hospital", "lat": 27.70, "lon": 68.86},
    "notified_at": "2026-01-01T09:17:01Z", "respond_by": "2026-01-01T09:18:01Z",
}


# ---------------------------------------------------------------- payload (UC-08 step 1)
def test_payload_has_what_uc08_shows_the_driver() -> None:
    a = DriverAssignmentOut.model_validate(PAYLOAD)
    assert (a.incident_type, a.severity, a.patients) == ("accident", "high", 6)
    assert a.location.source == "gps" and a.hospital is not None
    assert DriverAssignmentOut.model_validate_json(a.model_dump_json()) == a


def test_payload_allows_unknowns_after_an_ai_failure() -> None:
    a = DriverAssignmentOut.model_validate({
        **PAYLOAD, "incident_type": None, "severity": None, "patients": None, "eta_seconds": None,
        "hospital": None, "location": {"text": "near the market", "source": "text"},
    })
    assert a.incident_type is None and a.location.lat is None


@pytest.mark.parametrize("bad", [
    {"respond_by": "2026-01-01T09:17:00Z"},  # before the alert
    {"notified_at": None},  # respond_by without an alert time
    {"patients": -1}, {"eta_seconds": -1}, {"status": "on_scene"}, {"reference_no": "123"},
    {"eta_is_approximate": None}, {"extra": 1},
])
def test_invalid_payloads_rejected(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DriverAssignmentOut.model_validate({**PAYLOAD, **bad})


def test_answer_limit_default_is_60_seconds() -> None:
    assert DEFAULT_ANSWER_LIMIT_SECONDS == 60


# ---------------------------------------------------------------- assignment status
ALLOWED = {
    (A.APPROVED, A.ACCEPTED), (A.APPROVED, A.DECLINED), (A.APPROVED, A.TIMED_OUT), (A.APPROVED, A.CANCELLED),
    (A.ACCEPTED, A.COMPLETED), (A.ACCEPTED, A.CANCELLED),
}


@pytest.mark.parametrize("current", list(A), ids=str)
@pytest.mark.parametrize("new", list(A), ids=str)
def test_assignment_transitions_exactly_as_contracted(current: A, new: A) -> None:
    if (current, new) in ALLOWED:
        check_assignment_transition(current, new)
    else:
        with pytest.raises(InvalidTransition):
            check_assignment_transition(current, new)


def test_open_statuses_are_approved_and_accepted() -> None:
    """Must equal the partial unique index on assignments (one open assignment per vehicle, NFR-S6)."""
    assert OPEN_ASSIGNMENT_STATUSES == {A.APPROVED, A.ACCEPTED}
    assert set(ASSIGNMENT_TRANSITIONS) == set(A)


def test_vehicle_status_follows_the_assignment() -> None:
    assert VEHICLE_STATUS_FOR_ASSIGNMENT == {
        A.APPROVED: V.ASSIGNED, A.ACCEPTED: V.EN_ROUTE, A.DECLINED: V.AVAILABLE,
        A.TIMED_OUT: V.AVAILABLE, A.CANCELLED: V.AVAILABLE, A.COMPLETED: V.AVAILABLE,
    }


# ---------------------------------------------------------------- trip steps (UC-09)
def test_full_trip_through_the_hospital() -> None:
    status = V.EN_ROUTE
    for step, expected in [
        (TripStatus.ON_SCENE, V.ON_SCENE), (TripStatus.PICKED_UP, V.TRANSPORTING),
        (TripStatus.AT_HOSPITAL, V.AT_HOSPITAL), (TripStatus.AVAILABLE, V.AVAILABLE),
    ]:
        status = next_vehicle_status(status, step)
        assert status is expected


def test_no_patient_carried_on_scene_to_available() -> None:
    assert next_vehicle_status(V.ON_SCENE, TripStatus.AVAILABLE) is V.AVAILABLE


@pytest.mark.parametrize("current", list(V), ids=str)
@pytest.mark.parametrize("step", list(TripStatus), ids=str)
def test_every_other_trip_step_is_rejected(current: V, step: TripStatus) -> None:
    if (current, step) in TRIP_TRANSITIONS:
        assert next_vehicle_status(current, step) in V
    else:
        with pytest.raises(InvalidTransition):
            next_vehicle_status(current, step)


def test_trip_steps_vocabulary() -> None:
    assert [s.value for s in TripStatus] == ["on_scene", "picked_up", "at_hospital", "available"]
    assert len(TRIP_TRANSITIONS) == 5
