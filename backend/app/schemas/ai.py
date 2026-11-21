"""Contract C-2: what each AI step receives and returns (task B1-A2-01).

Field lists follow IMPLEMENTATION_PLAN.md B1-A2-01; vocabularies are reused from contract C-1
(``app.schemas.enums``). Where the plan text differed from C-1 v1, C-1 wins (DECISIONS_LOG, C-2
notes): duplicate decisions use ``auto_linked``/``possible``/``separate``, and the route field is
``route_geometry``.

Rules baked into the types, so invalid model output can never drive dispatch:
  * Every model rejects unknown fields (``extra="forbid"``).
  * Every confidence and similarity is 0..1; trust score and match confidence are 0..100.
  * Unknown values are explicit ``None``; a location is never guessed (``location_words`` is
    ``None`` when the report does not say where).
  * Agents recommend only. Nothing here sets an incident status, locks a vehicle or dispatches.

Thresholds that the admin can change (trust tiers, duplicate 85/60, vehicle rules) are NOT checked
here: they live in the settings and in the agents (SRS Appendix C, UC-12).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import Channel, DuplicateDecision, IncidentType, Severity, TrustTier, VehicleType

Confidence = Annotated[float, Field(ge=0, le=1)]
Count = Annotated[int, Field(ge=0)]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ C-2 vocabularies
class GeocodeSource(StrEnum):
    """Which step produced the coordinates (more detailed than C-1 ``LocationSource``).

    Mapping to C-1: ``gps`` -> ``gps``; ``gazetteer`` and ``nominatim`` -> ``text``; ``unknown`` -> ``unknown``.
    """

    GAZETTEER = "gazetteer"
    NOMINATIM = "nominatim"
    GPS = "gps"
    UNKNOWN = "unknown"


class TrustAction(StrEnum):
    """What the pipeline does after trust scoring (SRS Table 7.3.2)."""

    CONTINUE = "continue"
    CONTINUE_AND_CONFIRM = "continue_and_confirm"
    REVIEW_QUEUE = "review_queue"
    URGENT_WITH_WARNING = "urgent_with_warning"


class RoutingMode(StrEnum):
    """How ETAs were computed: OSRM routes, or straight-line distance when routing is down (UC-05 5a)."""

    OSRM = "osrm"
    STRAIGHT_LINE = "straight_line"


AgentDuplicateDecision = Literal[
    DuplicateDecision.AUTO_LINKED, DuplicateDecision.POSSIBLE, DuplicateDecision.SEPARATE
]
"""The Coordination Agent may only propose these; ``confirmed``/``rejected`` are dispatcher decisions.
Values are C-1 ``DuplicateDecision`` members, and the exported JSON Schema lists only these three."""

AGENT_DUPLICATE_DECISIONS = frozenset(get_args(AgentDuplicateDecision))


class GeoPoint(_Contract):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


# ------------------------------------------------------------------ Triage
class TriageInput(_Contract):
    """What the worker gives the Triage Agent: the report text (typed, SMS or transcript) only.

    The model never sees caller history, trust data or vehicle availability.
    """

    incident_id: int
    text: str = Field(min_length=1)
    channel: Channel
    language_hint: str | None = None
    caller_gps: GeoPoint | None = None
    location_text: str | None = None


class TriageResult(_Contract):
    """Triage Agent output. Every key must be present; ``None`` means "the report does not say"."""

    language: str | None
    language_confidence: Confidence | None
    incident_type: IncidentType | None
    type_confidence: Confidence | None
    severity: Severity | None
    severity_confidence: Confidence | None
    victims_estimate: Count | None
    victims_confidence: Confidence | None
    location_words: str | None = Field(min_length=1)
    has_real_details: bool
    vague_or_joking: bool
    missing_fields: list[str]
    overall_confidence: Confidence
    transcript_unclear: bool
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    latency_ms: Count


# ------------------------------------------------------------------ Geocoding
class GeocodeResult(_Contract):
    """Where the incident is, and which step found it. ``unknown`` means no coordinates."""

    lat: float | None = Field(ge=-90, le=90)
    lon: float | None = Field(ge=-180, le=180)
    source: GeocodeSource
    matched_name: str | None
    distance_to_gps_m: Count | None = None

    @model_validator(mode="after")
    def _coordinates_match_source(self) -> GeocodeResult:
        has_point = self.lat is not None and self.lon is not None
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must both be set or both be empty")
        if self.source is GeocodeSource.UNKNOWN and has_point:
            raise ValueError("source 'unknown' must not carry coordinates")
        if self.source is not GeocodeSource.UNKNOWN and not has_point:
            raise ValueError(f"source '{self.source}' requires lat and lon")
        return self


# ------------------------------------------------------------------ Trust (rule-based, no LLM)
class TrustSignal(_Contract):
    """One trust rule that fired, its points and the reason (SDS Table 6.3: "keeps a reason for each point")."""

    code: str = Field(min_length=1)
    points: int
    detail: str = Field(min_length=1)


class TrustAssessment(_Contract):
    score: int = Field(ge=0, le=100)
    tier: TrustTier
    signals: list[TrustSignal]
    action: TrustAction


# ------------------------------------------------------------------ Coordination
class DuplicateCandidateResult(_Contract):
    """One open incident that may be the same event. Scores are 0..1; match confidence is 0..100."""

    candidate_incident_id: int
    distance_m: Count
    time_diff_s: Count
    s_dist: Confidence
    s_time: Confidence
    s_meaning: Confidence
    match_confidence: int = Field(ge=0, le=100)
    decision: AgentDuplicateDecision


# ------------------------------------------------------------------ Resource allocation
class VehicleRecommendation(_Contract):
    vehicle_id: int
    vehicle_type: VehicleType
    rank: int = Field(ge=1)
    eta_seconds: Count
    distance_meters: Count
    eta_is_approximate: bool
    is_spare: bool
    route_geometry: str | None = None


class AllocationResult(_Contract):
    """Vehicles needed per type, any shortage, and the ranked recommendation list (needed + spares)."""

    needed: dict[VehicleType, Count]
    victims_unknown_check: bool
    shortage: dict[VehicleType, Count] | None
    recommendations: list[VehicleRecommendation]
    hospital_id: int | None = None  # suggestion only; the rule is still open (D-018)
    routing_mode: RoutingMode

    @model_validator(mode="after")
    def _straight_line_etas_are_approximate(self) -> AllocationResult:
        if self.routing_mode is RoutingMode.STRAIGHT_LINE and not all(
            r.eta_is_approximate for r in self.recommendations
        ):
            raise ValueError("straight_line routing: every ETA must be marked approximate")
        return self


C2_MODELS: tuple[type[BaseModel], ...] = (
    TriageInput,
    TriageResult,
    GeocodeResult,
    TrustAssessment,
    DuplicateCandidateResult,
    VehicleRecommendation,
    AllocationResult,
)
"""Every top-level C-2 schema; each has an example and an exported JSON Schema under tests/fixtures."""
