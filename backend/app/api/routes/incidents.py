"""Dispatcher incident queue, detail, edit and audio (UC-06, UC-01).
Queue and detail are built (B1-A1-20, read-only); edit and audio are 501 stubs until their tasks."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DISPATCHER, get_db
from app.api.errors import ERROR_RESPONSES, ApiError, NotImplementedYet
from app.schemas.enums import IncidentStatus, Severity
from app.schemas.incident import IncidentDetailOut, IncidentSummaryOut
from app.services import incidents as service

router = APIRouter(prefix="/incidents", tags=["incidents"], responses=ERROR_RESPONSES, dependencies=[Depends(DISPATCHER)])

SeverityFilter = Literal["critical", "high", "medium", "low", "unknown"]


@router.get("", response_model=list[IncidentSummaryOut])
async def list_incidents(
    status: list[IncidentStatus] | None = Query(None, description="Only these statuses (repeat the parameter)"),
    severity: list[SeverityFilter] | None = Query(None, description="Only these severities; 'unknown' = not set yet"),
    include_closed: bool = Query(False, description="Also show closed and fake reports (ignored when status is given)"),
    limit: int = Query(service.DEFAULT_LIMIT, ge=1, le=service.MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[IncidentSummaryOut]:
    """Incident queue: open reports by default, critical → high → unknown → medium → low, then the
    longest-waiting first. Read-only."""
    severities = None if not severity else [None if s == "unknown" else Severity(s) for s in severity]
    return await service.list_incidents(db, statuses=status, severities=severities, include_closed=include_closed,
                                        limit=limit, offset=offset)


@router.get("/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(incident_id: int, db: AsyncSession = Depends(get_db)) -> IncidentDetailOut:
    """Everything the review screen needs: the report as sent, AI results with their confidence, trust
    reasons, current recommendations (with plates), duplicates and assignments. Read-only."""
    detail = await service.get_incident(db, incident_id)
    if detail is None:
        raise ApiError(404, "No such incident.", code="not_found")
    return detail


@router.patch("/{incident_id}", response_model=IncidentDetailOut)
async def edit_incident(incident_id: int):
    """Edit type, severity, victims or location; the recommendation is calculated again."""
    raise NotImplementedYet("B1-A1-21")


@router.get("/{incident_id}/audio")
async def get_incident_audio(incident_id: int):
    raise NotImplementedYet("B1-A1-17")
