"""Contract C-5: live-update events and the worker's NOTIFY payload (task B1-A1-05).

Sources: SDS v1.1 Table 4.4 (event names, channels, data), Table 4.3 (``GET /api/v1/ws``), D-010
(the worker talks to the API only through the database; NOTIFY payloads stay small: event name and
incident id, the API re-reads the row).

Every WebSocket message is ``{event, v, occurred_at, data}``. Dispatchers listen on ``dispatchers``;
each driver on ``driver:<user_id>``. ``EVENTS`` maps each event to its data model and channel and is
the single source of truth (``docs/API_CONTRACT.md`` §4 is checked against it).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.assignment import DriverAssignmentOut
from app.schemas.enums import PipelineState, VehicleType
from app.schemas.incident import AssignmentOut, IncidentSummaryOut

ENVELOPE_VERSION = 1
NOTIFY_CHANNEL = "incident_events"  # worker -> API events (D-010)
JOB_NOTIFY_CHANNEL = "report_pending"  # API -> worker: a new job is waiting (B1-A1-16); payload = incident id


class EventName(StrEnum):
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_AI_FAILED = "incident.ai_failed"
    REVIEW_ITEM_ADDED = "review.item_added"
    REVIEW_ITEM_RESOLVED = "review.item_resolved"
    DUPLICATE_CANDIDATE = "duplicate.candidate"
    RECOMMENDATION_READY = "recommendation.ready"
    DISPATCH_APPROVED = "dispatch.approved"
    ASSIGNMENT_NEW = "assignment.new"
    ASSIGNMENT_UPDATED = "assignment.updated"
    ASSIGNMENT_ACCEPTED = "assignment.accepted"
    ASSIGNMENT_DECLINED = "assignment.declined"
    ASSIGNMENT_TIMED_OUT = "assignment.timed_out"
    ASSIGNMENT_STATUS_CHANGED = "assignment.status_changed"
    VEHICLE_POSITION = "vehicle.position"
    VEHICLE_SIGNAL_LOST = "vehicle.signal_lost"
    VEHICLE_SIGNAL_RESTORED = "vehicle.signal_restored"
    SYSTEM_SERVICE_STATUS = "system.service_status"


class Audience(StrEnum):
    DISPATCHERS = "dispatchers"
    DRIVER = "driver"  # the concrete channel is driver:<user_id>, see driver_channel()


class PipelineStage(StrEnum):
    """A step of the AI pipeline, in order (SDS Table 6.3, AgentOrchestrator)."""

    SPEECH_TO_TEXT = "speech_to_text"
    GEOCODING = "geocoding"
    TRIAGE = "triage"
    TRUST = "trust"
    COORDINATION = "coordination"
    ALLOCATION = "allocation"


class ServiceName(StrEnum):
    """Services shown on the dashboard status bar (SDS Table 4.3, ``GET /health``)."""

    API = "api"
    DATABASE = "database"
    AI_WORKER = "ai_worker"
    OSRM = "osrm"
    LLM = "llm"
    GEOCODER = "geocoder"


class ServiceState(StrEnum):
    UP = "up"
    DOWN = "down"


def driver_channel(user_id: int) -> str:
    return f"driver:{user_id}"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ event data (SDS Table 4.4 "Data")
class IncidentUpdatedData(_Contract):
    incident_id: int
    changed_fields: list[str]
    pipeline_state: PipelineState


class IncidentAiFailedData(_Contract):
    """Manual mode: the dispatcher works by hand (safety rule 7)."""

    incident_id: int
    failed_step: PipelineStage


class ReviewItemData(_Contract):
    incident_id: int
    reasons: list[str]


class DuplicateCandidateData(_Contract):
    incident_id: int
    candidate_incident_id: int
    match_confidence: int = Field(ge=0, le=100)


class RecommendationReadyData(_Contract):
    incident_id: int
    shortage: dict[VehicleType, int] | None  # None = enough vehicles


class DispatchApprovedData(_Contract):
    incident_id: int
    assignments: list[AssignmentOut] = Field(min_length=1)


class VehiclePositionData(_Contract):
    vehicle_id: int
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmh: float | None = Field(ge=0)
    recorded_at: AwareDatetime


class LastPosition(_Contract):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    recorded_at: AwareDatetime


class VehicleSignalData(_Contract):
    vehicle_id: int
    last_position: LastPosition | None  # None if the vehicle never sent a position


class ServiceStatusData(_Contract):
    services: dict[ServiceName, ServiceState] = Field(min_length=1)


EVENTS: dict[EventName, tuple[type[BaseModel], Audience]] = {
    EventName.INCIDENT_CREATED: (IncidentSummaryOut, Audience.DISPATCHERS),
    EventName.INCIDENT_UPDATED: (IncidentUpdatedData, Audience.DISPATCHERS),
    EventName.INCIDENT_AI_FAILED: (IncidentAiFailedData, Audience.DISPATCHERS),
    EventName.REVIEW_ITEM_ADDED: (ReviewItemData, Audience.DISPATCHERS),
    EventName.REVIEW_ITEM_RESOLVED: (ReviewItemData, Audience.DISPATCHERS),
    EventName.DUPLICATE_CANDIDATE: (DuplicateCandidateData, Audience.DISPATCHERS),
    EventName.RECOMMENDATION_READY: (RecommendationReadyData, Audience.DISPATCHERS),
    EventName.DISPATCH_APPROVED: (DispatchApprovedData, Audience.DISPATCHERS),
    EventName.ASSIGNMENT_NEW: (DriverAssignmentOut, Audience.DRIVER),
    EventName.ASSIGNMENT_UPDATED: (DriverAssignmentOut, Audience.DRIVER),
    EventName.ASSIGNMENT_ACCEPTED: (AssignmentOut, Audience.DISPATCHERS),
    EventName.ASSIGNMENT_DECLINED: (AssignmentOut, Audience.DISPATCHERS),
    EventName.ASSIGNMENT_TIMED_OUT: (AssignmentOut, Audience.DISPATCHERS),
    EventName.ASSIGNMENT_STATUS_CHANGED: (AssignmentOut, Audience.DISPATCHERS),
    EventName.VEHICLE_POSITION: (VehiclePositionData, Audience.DISPATCHERS),
    EventName.VEHICLE_SIGNAL_LOST: (VehicleSignalData, Audience.DISPATCHERS),
    EventName.VEHICLE_SIGNAL_RESTORED: (VehicleSignalData, Audience.DISPATCHERS),
    EventName.SYSTEM_SERVICE_STATUS: (ServiceStatusData, Audience.DISPATCHERS),
}

WORKER_EVENTS = frozenset(
    {
        EventName.INCIDENT_UPDATED,
        EventName.INCIDENT_AI_FAILED,
        EventName.REVIEW_ITEM_ADDED,
        EventName.REVIEW_ITEM_RESOLVED,
        EventName.DUPLICATE_CANDIDATE,
        EventName.RECOMMENDATION_READY,
    }
)
"""Events the AI worker may raise (SDS Table 4.4 "Sent by": AI worker). It sends them only by NOTIFY."""


class EventEnvelope(_Contract):
    """One WebSocket message. ``data`` is validated against the model registered for ``event``."""

    event: EventName
    v: Literal[1] = ENVELOPE_VERSION
    occurred_at: AwareDatetime
    data: Any

    @model_validator(mode="after")
    def _data_matches_event(self) -> EventEnvelope:
        model, _ = EVENTS[self.event]
        raw = self.data.model_dump(mode="json") if isinstance(self.data, BaseModel) else self.data
        self.data = model.model_validate(raw)
        return self

    @property
    def audience(self) -> Audience:
        return EVENTS[self.event][1]


class NotifyPayload(_Contract):
    """Body of ``NOTIFY incident_events`` from the worker: event name and incident id only (D-010)."""

    event: EventName
    incident_id: int

    @model_validator(mode="after")
    def _worker_events_only(self) -> NotifyPayload:
        if self.event not in WORKER_EVENTS:
            raise ValueError(f"the worker may not raise '{self.event}'")
        return self
