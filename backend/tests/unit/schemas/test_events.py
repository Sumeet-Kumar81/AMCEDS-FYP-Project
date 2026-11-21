"""Contract C-5 tests (B1-A1-05): event names, envelope, data models and the worker's NOTIFY payload."""
import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.events import (
    ENVELOPE_VERSION,
    EVENTS,
    NOTIFY_CHANNEL,
    WORKER_EVENTS,
    Audience,
    EventEnvelope,
    EventName,
    NotifyPayload,
    PipelineStage,
    ServiceName,
    ServiceState,
    driver_channel,
)
from app.schemas.incident import IncidentSummaryOut

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"
DOC = Path(os.environ.get("API_CONTRACT_DOC", Path(__file__).resolve().parents[4] / "docs" / "API_CONTRACT.md"))
WHEN = "2026-01-01T09:15:30Z"

SDS_TABLE_4_4 = [
    "incident.created", "incident.updated", "incident.ai_failed", "review.item_added", "review.item_resolved",
    "duplicate.candidate", "recommendation.ready", "dispatch.approved", "assignment.new", "assignment.updated",
    "assignment.accepted", "assignment.declined", "assignment.timed_out", "assignment.status_changed",
    "vehicle.position", "vehicle.signal_lost", "vehicle.signal_restored", "system.service_status",
]


def incident_detail() -> dict[str, Any]:
    return json.loads((FIXTURES / "incident_detail.json").read_text(encoding="utf-8"))


ASSIGNMENT = incident_detail()["assignments"][0]
SUMMARY = {k: v for k, v in incident_detail().items() if k in IncidentSummaryOut.model_fields}
DRIVER_ASSIGNMENT = {
    "assignment_id": 7, "incident_id": 123, "reference_no": "INC-000123", "status": "approved",
    "incident_type": "accident", "severity": "high",
    "location": {"lat": 27.7052, "lon": 68.8574, "text": "near the market", "source": "gps"},
    "patients": 6, "eta_seconds": 420, "eta_is_approximate": False, "hospital": None,
    "notified_at": "2026-01-01T09:17:01Z", "respond_by": "2026-01-01T09:18:01Z",
}
EXAMPLE_DATA: dict[EventName, dict[str, Any]] = {
    EventName.INCIDENT_CREATED: SUMMARY,
    EventName.INCIDENT_UPDATED: {"incident_id": 123, "changed_fields": ["severity"], "pipeline_state": "done"},
    EventName.INCIDENT_AI_FAILED: {"incident_id": 123, "failed_step": "triage"},
    EventName.REVIEW_ITEM_ADDED: {"incident_id": 123, "reasons": ["low_confidence"]},
    EventName.REVIEW_ITEM_RESOLVED: {"incident_id": 123, "reasons": []},
    EventName.DUPLICATE_CANDIDATE: {"incident_id": 123, "candidate_incident_id": 120, "match_confidence": 72},
    EventName.RECOMMENDATION_READY: {"incident_id": 123, "shortage": None},
    EventName.DISPATCH_APPROVED: {"incident_id": 123, "assignments": [ASSIGNMENT]},
    EventName.ASSIGNMENT_NEW: DRIVER_ASSIGNMENT,
    EventName.ASSIGNMENT_UPDATED: DRIVER_ASSIGNMENT,
    EventName.ASSIGNMENT_ACCEPTED: ASSIGNMENT,
    EventName.ASSIGNMENT_DECLINED: ASSIGNMENT,
    EventName.ASSIGNMENT_TIMED_OUT: ASSIGNMENT,
    EventName.ASSIGNMENT_STATUS_CHANGED: ASSIGNMENT,
    EventName.VEHICLE_POSITION: {"vehicle_id": 5, "lat": 27.7, "lon": 68.85, "speed_kmh": 42.5, "recorded_at": WHEN},
    EventName.VEHICLE_SIGNAL_LOST: {"vehicle_id": 5, "last_position": {"lat": 27.7, "lon": 68.85, "recorded_at": WHEN}},
    EventName.VEHICLE_SIGNAL_RESTORED: {"vehicle_id": 5, "last_position": None},
    EventName.SYSTEM_SERVICE_STATUS: {"services": {"api": "up", "database": "up", "osrm": "down"}},
}


# ---------------------------------------------------------------- names and registry
def test_event_names_match_sds_table_4_4() -> None:
    assert [e.value for e in EventName] == SDS_TABLE_4_4


def test_every_event_has_a_data_model_and_a_channel() -> None:
    assert set(EVENTS) == set(EventName)


def test_only_assignment_new_and_updated_go_to_the_driver() -> None:
    to_driver = {e for e, (_, audience) in EVENTS.items() if audience is Audience.DRIVER}
    assert to_driver == {EventName.ASSIGNMENT_NEW, EventName.ASSIGNMENT_UPDATED}
    assert driver_channel(42) == "driver:42"


def test_vocabularies() -> None:
    assert [s.value for s in PipelineStage] == [
        "speech_to_text", "geocoding", "triage", "trust", "coordination", "allocation",
    ]
    assert [s.value for s in ServiceName] == ["api", "database", "ai_worker", "osrm", "llm", "geocoder"]
    assert [s.value for s in ServiceState] == ["up", "down"]


# ---------------------------------------------------------------- envelope
@pytest.mark.parametrize("event", list(EventName), ids=str)
def test_every_event_round_trips_through_the_envelope(event: EventName) -> None:
    msg = {"event": event.value, "v": 1, "occurred_at": WHEN, "data": EXAMPLE_DATA[event]}
    envelope = EventEnvelope.model_validate(msg)
    assert isinstance(envelope.data, EVENTS[event][0])
    assert EventEnvelope.model_validate_json(envelope.model_dump_json()) == envelope
    assert envelope.audience is EVENTS[event][1]


def test_envelope_accepts_a_model_instance_as_data() -> None:
    summary = IncidentSummaryOut.model_validate(SUMMARY)
    envelope = EventEnvelope(event=EventName.INCIDENT_CREATED, occurred_at=WHEN, data=summary)
    assert envelope.v == ENVELOPE_VERSION == 1 and envelope.data == summary


@pytest.mark.parametrize("event,data", [
    (EventName.INCIDENT_CREATED, {"incident_id": 1}),
    (EventName.DUPLICATE_CANDIDATE, {"incident_id": 1, "candidate_incident_id": 2, "match_confidence": 101}),
    (EventName.DISPATCH_APPROVED, {"incident_id": 1, "assignments": []}),
    (EventName.INCIDENT_AI_FAILED, {"incident_id": 1, "failed_step": "dispatch"}),
    (EventName.INCIDENT_UPDATED, {"incident_id": 1, "changed_fields": [], "pipeline_state": "retrust"}),
    (EventName.SYSTEM_SERVICE_STATUS, {"services": {}}),
    (EventName.SYSTEM_SERVICE_STATUS, {"services": {"redis": "up"}}),
    (EventName.VEHICLE_POSITION, {"vehicle_id": 5, "lat": 91, "lon": 0, "speed_kmh": 1, "recorded_at": WHEN}),
    (EventName.ASSIGNMENT_NEW, ASSIGNMENT),  # a dispatcher-side shape sent to the driver channel
])
def test_data_must_match_the_event(event: EventName, data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate({"event": event.value, "occurred_at": WHEN, "data": data})


@pytest.mark.parametrize("bad", [
    {"event": "incident.deleted"}, {"v": 2}, {"occurred_at": "2026-01-01T09:15:30"}, {"extra": 1},
])
def test_envelope_rejects_bad_headers(bad: dict[str, Any]) -> None:
    msg = {"event": "review.item_added", "v": 1, "occurred_at": WHEN, "data": {"incident_id": 1, "reasons": []}}
    with pytest.raises(ValidationError):
        EventEnvelope.model_validate({**msg, **bad})


# ---------------------------------------------------------------- worker NOTIFY (D-010)
def test_notify_channel_name() -> None:
    assert NOTIFY_CHANNEL == "incident_events"


# SDS v1.1 Table 4.4, "Sent by" contains "AI worker". Written out, not derived from WORKER_EVENTS,
# so widening WORKER_EVENTS (e.g. letting the worker announce a dispatch) fails here.
SDS_AI_WORKER_EVENTS = {
    "incident.updated", "incident.ai_failed", "review.item_added", "review.item_resolved",
    "duplicate.candidate", "recommendation.ready",
}


def test_worker_events_are_exactly_the_sds_ai_worker_events() -> None:
    assert {e.value for e in WORKER_EVENTS} == SDS_AI_WORKER_EVENTS


@pytest.mark.parametrize("event", sorted(SDS_AI_WORKER_EVENTS))
def test_worker_may_notify_its_events(event: str) -> None:
    payload = NotifyPayload(event=event, incident_id=1)
    assert len(payload.model_dump_json()) < 8000  # PostgreSQL NOTIFY payload limit


@pytest.mark.parametrize("event", sorted(set(SDS_TABLE_4_4) - SDS_AI_WORKER_EVENTS))
def test_worker_may_not_raise_api_events(event: str) -> None:
    with pytest.raises(ValidationError):
        NotifyPayload(event=event, incident_id=1)


def test_notify_payload_carries_only_event_and_id() -> None:
    assert set(NotifyPayload.model_fields) == {"event", "incident_id"}
    with pytest.raises(ValidationError):
        NotifyPayload.model_validate({"event": "incident.updated", "incident_id": 1, "data": {}})


# ---------------------------------------------------------------- docs/API_CONTRACT.md §4
def test_contract_document_lists_the_same_events_and_channels() -> None:
    if not DOC.exists():
        pytest.skip(f"docs/API_CONTRACT.md not visible here ({DOC}); runs in CI and with the repo mounted")
    rows = re.findall(r"^\| `([a-z_]+\.[a-z_]+)` \| ([^|]+?) \|", DOC.read_text(encoding="utf-8"), re.M)
    documented = {name: ("driver" if chan.startswith("driver:") else chan) for name, chan in rows}
    assert documented == {e.value: audience.value for e, (_, audience) in EVENTS.items()}
