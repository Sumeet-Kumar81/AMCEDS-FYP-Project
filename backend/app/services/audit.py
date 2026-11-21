"""Audit service (B1-A1-13): one way to write the audit log (NFR-S9, NFR-C10).

``record`` adds the row inside the caller's transaction and does not commit. So the business change
and its audit row are saved together or not at all: no audit row means no commit, and a rolled-back
change leaves no audit row. Rows can never be changed afterwards (database trigger, migration 0002).

Every state-changing service must call ``record`` with an action from ``AuditAction``.
"""
from __future__ import annotations

import json
import logging
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditAction(StrEnum):
    """The action catalogue (IMPLEMENTATION_PLAN B1-A1-13). New actions are added here first."""

    REPORT_RECEIVED = "report.received"
    AI_TRANSCRIPT = "ai.transcript"
    AI_GEOCODE = "ai.geocode"
    AI_TRIAGE = "ai.triage"
    AI_TRUST = "ai.trust"
    AI_DUPLICATES = "ai.duplicates"
    AI_ALLOCATION = "ai.allocation"
    AI_FAILED = "ai.failed"
    INCIDENT_EDITED = "incident.edited"
    DUPLICATE_CONFIRMED = "duplicate.confirmed"
    DUPLICATE_REJECTED = "duplicate.rejected"
    REVIEW_DECISION = "review.decision"
    CONFIRMATION_SENT = "confirmation.sent"
    CONFIRMATION_ANSWERED = "confirmation.answered"
    DISPATCH_APPROVED = "dispatch.approved"
    ASSIGNMENT_ACCEPTED = "assignment.accepted"
    ASSIGNMENT_DECLINED = "assignment.declined"
    ASSIGNMENT_TIMED_OUT = "assignment.timed_out"
    ASSIGNMENT_STATUS_CHANGED = "assignment.status_changed"
    ASSIGNMENT_HOSPITAL_CHANGED = "assignment.hospital_changed"
    ASSIGNMENT_CANCELLED = "assignment.cancelled"
    VEHICLE_LOCKED = "vehicle.locked"
    VEHICLE_UNLOCKED = "vehicle.unlocked"
    SETTINGS_CHANGED = "settings.changed"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DISABLED = "user.disabled"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_LOCKED = "auth.locked"
    AUTH_LOGOUT = "auth.logout"


async def record(
    session: AsyncSession,
    action: AuditAction,
    *,
    user_id: int | None = None,
    incident_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> int:
    """Add one audit row to the current transaction and return its ``log_id``. Never commits.

    ``details`` must be JSON (dicts, lists, strings, numbers, booleans, None). Passwords, tokens and
    other secrets must never be put in it.
    """
    action = AuditAction(action)  # unknown actions raise ValueError
    if details is not None:
        json.dumps(details, allow_nan=False)  # raises TypeError/ValueError for non-JSON content
    row = AuditLog(action=action.value, user_id=user_id, incident_id=incident_id, details=details)
    session.add(row)
    await session.flush()
    logger.info("audit %s incident=%s user=%s", action.value, incident_id, user_id)
    return row.log_id
