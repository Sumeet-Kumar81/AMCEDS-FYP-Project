"""Contract C-1 (part 2): the Incident Record as the API returns it.

Field names follow SRS Table 3.4 / Appendix B (§7.2) and SDS v1.1 Tables 5.2, 5.7, 5.8 and 5.12.
Nothing here is invented: every field maps to a documented column or SRS field.

Rules baked into the types:
  * ``confidence`` is 0..1 in the API (the UI shows 0..100 %). ``trust_score`` is 0..100.
  * Timestamps must be timezone-aware (UTC on the wire).
  * Fields the AI has not filled yet are ``None`` (a new report has no type or severity).
    ``location`` is always present; an unknown location is ``source="unknown"``.
  * Output models reject unknown fields, so contract drift fails the tests.

``ai_details`` and ``allocation_summary`` are JSON objects whose inner shape belongs to contract
C-2 (``schemas/ai.py``, task B1-A2-01). They are deliberately typed as plain objects here.
"""
from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import (
    AssignmentStatus,
    Channel,
    DuplicateDecision,
    IncidentStatus,
    IncidentType,
    LocationSource,
    Severity,
    TrustTier,
    VehicleType,
)

REFERENCE_NO_PATTERN = r"^INC-\d{6,}$"  # D-004: "INC-" + at least six digits, e.g. INC-000123


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationOut(_Contract):
    """Incident location: coordinates (if known), address words, and where they came from.

    Always present on an incident; "no location" is ``source="unknown"``.
      * ``gps``     - lat and lon required.
      * ``text``    - address/landmark words required. Coordinates stay empty until the AI worker
                      geocodes them (D-011: no geocoding in the request path), then they are filled.
      * ``unknown`` - nothing required.
    lat and lon always come as a pair.
    """

    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    text: str | None = None
    source: LocationSource

    @model_validator(mode="after")
    def _check_source_rules(self) -> LocationOut:
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must both be set or both be empty")
        if self.source is LocationSource.GPS and self.lat is None:
            raise ValueError("source 'gps' requires lat and lon")
        if self.source is LocationSource.TEXT and not (self.text and self.text.strip()):
            raise ValueError("source 'text' requires the address or landmark words in 'text'")
        return self


class DispatcherDecisionOut(_Contract):
    """What the dispatcher approved, and when (SRS Table 3.4). Taken from ``assignments.approved_by/approved_at``."""

    approved_by: int
    approved_at: AwareDatetime


class TrustSignalOut(_Contract):
    """One trust rule that was applied, with its points and reason (SDS Table 5.2 ``trust_signals``).

    ``detail`` added in C-1 v1.1 to match C-2 ``TrustSignal``; optional so v1 data stays valid.
    """

    code: str
    points: int
    detail: str | None = None


class DuplicateCandidateOut(_Contract):
    """A possible or decided match with another open incident (SDS Table 5.12)."""

    duplicate_id: int
    candidate_incident_id: int
    match_confidence: int = Field(ge=0, le=100)
    distance_m: int | None = Field(default=None, ge=0)
    time_diff_s: int | None = Field(default=None, ge=0)
    similarity: float | None = Field(default=None, ge=0, le=1)
    decision: DuplicateDecision
    decided_by: int | None = None
    decided_at: AwareDatetime | None = None


class RecommendationOut(_Contract):
    """One recommended vehicle (SDS Table 5.7). The detail view carries the current round only."""

    rec_id: int
    vehicle_id: int
    rank: int = Field(ge=1)
    # Always present: when routing is down the ETA comes from straight-line distance and
    # eta_is_approximate is true (SRS UC-05 5a); it is never empty.
    eta_seconds: int = Field(ge=0)
    distance_meters: int = Field(ge=0)
    created_at: AwareDatetime
    vehicle_type: VehicleType
    eta_is_approximate: bool
    is_spare: bool
    route_geometry: str | None = None
    batch_no: int = Field(ge=1)  # recommendation rounds start at 1 (C-1 v1 note, DECISIONS_LOG)
    is_current: bool
    # C-1 v1.2 (F4): the vehicle's plate, so the dispatcher sees "SIM-AMB-01", not "vehicle 3".
    # Optional so v1/v1.1 data stays valid; filled from vehicles.plate_number by the incident API.
    plate_number: str | None = None


class AssignmentOut(_Contract):
    """One dispatched vehicle and its trip timeline (SDS Table 5.8)."""

    assignment_id: int
    vehicle_id: int
    approved_by: int
    hospital_id: int | None = None
    status: AssignmentStatus
    approved_at: AwareDatetime
    accepted_at: AwareDatetime | None = None
    on_scene_at: AwareDatetime | None = None
    picked_up_at: AwareDatetime | None = None
    at_hospital_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None
    notified_at: AwareDatetime | None = None
    decline_reason: str | None = None
    declined_at: AwareDatetime | None = None
    timed_out_at: AwareDatetime | None = None


class IncidentSummaryOut(_Contract):
    """A queue card: the fields of the Incident Record every list needs (SRS §7.2)."""

    incident_id: int
    reference_no: str = Field(pattern=REFERENCE_NO_PATTERN)
    channel: Channel
    received_at: AwareDatetime
    language: str | None = None
    location: LocationOut  # required; "no location" is source="unknown"
    incident_type: IncidentType | None = None
    severity: Severity | None = None
    victims_estimate: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    trust_score: int | None = Field(default=None, ge=0, le=100)
    trust_tier: TrustTier | None = None
    group_id: int | None = None
    status: IncidentStatus
    review_reasons: list[str] = Field(default_factory=list)


class IncidentDetailOut(IncidentSummaryOut):
    """The full record for the review screen (UC-06).

    The SRS §7.2 sample's ``vehicles`` ("recommended and assigned") is carried by two lists here:
    ``recommendations`` (current round) and ``assignments``.
    """

    original_text: str | None = None
    audio_ref: str | None = None
    reporter_name: str | None = None
    ai_details: dict[str, Any] | None = None
    trust_signals: list[TrustSignalOut] = Field(default_factory=list)
    allocation_summary: dict[str, Any] | None = None
    duplicate_candidates: list[DuplicateCandidateOut] = Field(default_factory=list)
    recommendations: list[RecommendationOut] = Field(default_factory=list)
    assignments: list[AssignmentOut] = Field(default_factory=list)
    dispatcher_decision: DispatcherDecisionOut | None = None
