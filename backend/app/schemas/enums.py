"""Contract C-1 (part 1): shared vocabularies.

Values are fixed by the approved decision D-005 (DECISIONS_LOG) and SDS v1.1 §5. They are stored
in the database as text with CHECK constraints (not native PostgreSQL enums) and travel through
the API and WebSocket as these exact lowercase strings.

Changing a value is a contract change: bump the C-1 version and tell every consumer
(AI agents, web, mobile, database migrations).
"""
from enum import StrEnum


class Channel(StrEnum):
    """How the report arrived (SRS Table 3.4). The Android app is ``app``, not ``mobile``."""

    VOICE = "voice"
    SMS = "sms"
    WEB = "web"
    APP = "app"


class IncidentStatus(StrEnum):
    """``incidents.status``. "Needs more information" is NEEDS_CHECK plus review reason ``missing_info``."""

    NEW = "new"
    TRIAGED = "triaged"
    NEEDS_CHECK = "needs_check"
    DISPATCHED = "dispatched"
    ON_SCENE = "on_scene"
    CLOSED = "closed"
    FAKE = "fake"


class IncidentType(StrEnum):
    ACCIDENT = "accident"
    FIRE = "fire"
    MEDICAL = "medical"
    OTHER = "other"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrustTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LocationSource(StrEnum):
    """Where the incident location came from. Lowercase per D-005 (the SRS §7.2 sample shows "GPS")."""

    GPS = "gps"
    TEXT = "text"
    UNKNOWN = "unknown"


class VehicleType(StrEnum):
    AMBULANCE = "ambulance"
    FIRE_TRUCK = "fire_truck"
    BACKUP = "backup"


class VehicleStatus(StrEnum):
    """``vehicles.status`` (``at_hospital`` added by D-005 for UC-09)."""

    AVAILABLE = "available"
    ASSIGNED = "assigned"
    EN_ROUTE = "en_route"
    ON_SCENE = "on_scene"
    TRANSPORTING = "transporting"
    AT_HOSPITAL = "at_hospital"
    OFFLINE = "offline"


class AssignmentStatus(StrEnum):
    """``assignments.status`` (``cancelled`` added by D-005: vehicle freed by the dispatcher)."""

    APPROVED = "approved"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TIMED_OUT = "timed_out"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PipelineState(StrEnum):
    """``incidents.pipeline_state``: state of the AI job (D-005, D-010)."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    REALLOCATE = "reallocate"


class DuplicateDecision(StrEnum):
    """``duplicate_candidates.decision`` (SDS v1.1 Table 5.12)."""

    AUTO_LINKED = "auto_linked"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SEPARATE = "separate"
