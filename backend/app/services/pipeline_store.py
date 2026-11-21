"""Contract C-6: the AI worker's only door to the database (task B1-A1-05). INTERFACE ONLY.

This module defines *what* the worker may read and write. There is no database code here yet:
the PostgreSQL implementation comes in B1-A1-19, and the AI agents are tested against a fake that
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
