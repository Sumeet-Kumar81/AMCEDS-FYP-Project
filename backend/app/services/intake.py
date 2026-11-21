"""Intake service (B1-A1-16; SRS UC-01, NFR-P12; D-011): save the report first, AI later.

``create_report`` does everything in the caller's transaction and does not commit:
  1. find or create the caller (phone first, then device id);
  2. insert the incident: status ``new``, ``pipeline_state = pending``; location from GPS, else the
     address words, else ``unknown`` with review reason ``location_unknown``; caller GPS kept apart;
     the settings in force stored as ``settings_snapshot`` (new settings apply to new incidents only);
  3. audit ``report.received``;
  4. ``NOTIFY report_pending`` so the AI worker wakes up (sent by PostgreSQL only at commit).
The reference number is computed by PostgreSQL from the saved row, so it exists only if the row does.
No geocoding, speech-to-text or AI happens here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Caller, Incident
from app.schemas.enums import IncidentStatus, LocationSource, PipelineState
from app.schemas.events import JOB_NOTIFY_CHANNEL
from app.schemas.report import ReportIn
from app.services.audit import AuditAction, record
from app.services.settings import get_snapshot

logger = logging.getLogger(__name__)


def _point(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


async def find_by_client_request_id(db: AsyncSession, client_request_id: str) -> Incident | None:
    return await db.scalar(select(Incident).where(Incident.client_request_id == client_request_id))


async def _caller(db: AsyncSession, phone: str | None, device_id: str | None, now: datetime) -> Caller | None:
    """Same caller = same phone number, otherwise same device. Missing identifiers are filled in only
    when no other caller already has them (both are unique when present)."""
    if phone is None and device_id is None:
        return None
    by_phone = await db.scalar(select(Caller).where(Caller.phone_number == phone)) if phone else None
    by_device = await db.scalar(select(Caller).where(Caller.device_id == device_id)) if device_id else None
    caller = by_phone or by_device
    if caller is None:
        caller = Caller(phone_number=phone, device_id=device_id)
        db.add(caller)
    else:
        if phone and caller.phone_number is None:
            caller.phone_number = phone  # by_phone is None here, so the number is free
        if device_id and caller.device_id is None and by_device is None:
            caller.device_id = device_id
    caller.last_report_at = now
    await db.flush()
    return caller


async def create_report(db: AsyncSession, body: ReportIn) -> tuple[Incident, bool]:
    """Return ``(incident, created)``; ``created`` is False for a resend with a known client_request_id."""
    if body.client_request_id:
        existing = await find_by_client_request_id(db, body.client_request_id)
        if existing is not None:
            logger.info("resend of client_request_id %s -> %s", body.client_request_id, existing.reference_no)
            return existing, False

    now = datetime.now(timezone.utc)
    caller = await _caller(db, body.phone_digits, body.device_id, now)
    has_gps = body.lat is not None and body.lon is not None
    if has_gps:
        source = LocationSource.GPS
    elif body.address_text:
        source = LocationSource.TEXT
    else:
        source = LocationSource.UNKNOWN

    incident = Incident(
        client_request_id=body.client_request_id,
        caller_id=caller.caller_id if caller else None,
        channel=body.channel.value,
        received_at=now,
        original_text=body.description,
        reporter_name=body.reporter_name,
        location=_point(body.lat, body.lon) if has_gps else None,
        caller_gps=_point(body.lat, body.lon) if has_gps else None,
        location_text=body.address_text,
        location_source=source.value,
        status=IncidentStatus.NEW.value,
        pipeline_state=PipelineState.PENDING.value,
        review_reasons=["location_unknown"] if source is LocationSource.UNKNOWN else [],
        settings_snapshot=await get_snapshot(db),
    )
    db.add(incident)
    await db.flush()
    await db.refresh(incident, ["reference_no", "received_at"])
    await record(db, AuditAction.REPORT_RECEIVED, incident_id=incident.incident_id, details={
        "channel": incident.channel, "location_source": source.value,
        "client_request_id": body.client_request_id, "caller_id": incident.caller_id,
    })
    await db.execute(text("SELECT pg_notify(:channel, :payload)"),
                     {"channel": JOB_NOTIFY_CHANNEL, "payload": str(incident.incident_id)})
    return incident, True
