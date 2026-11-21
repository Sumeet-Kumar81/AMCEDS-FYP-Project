"""SQLAlchemy models: the database schema v1 (SDS v1.1 §5, Tables 5.1–5.15, decision D-004).

One module per area: ``user`` (users, user_sessions), ``caller``, ``incident`` (incidents,
incident_groups), ``fleet`` (vehicles, vehicle_locations, hospitals), ``dispatch`` (recommendations,
assignments), ``audit`` (audit_logs, settings, worker_heartbeats), ``review`` (duplicate_candidates,
confirmation_requests). Importing this package registers every table on ``Base.metadata``; schema
changes are made only through Alembic migrations (``backend/migrations/``).
"""
from app.models.audit import AuditLog, Setting, WorkerHeartbeat
from app.models.caller import Caller
from app.models.dispatch import Assignment, Recommendation
from app.models.fleet import Hospital, Vehicle, VehicleLocation
from app.models.incident import Incident, IncidentGroup
from app.models.review import ConfirmationRequest, DuplicateCandidate
from app.models.user import User, UserSession

__all__ = [
    "Assignment",
    "AuditLog",
    "Caller",
    "ConfirmationRequest",
    "DuplicateCandidate",
    "Hospital",
    "Incident",
    "IncidentGroup",
    "Recommendation",
    "Setting",
    "User",
    "UserSession",
    "Vehicle",
    "VehicleLocation",
    "WorkerHeartbeat",
]
