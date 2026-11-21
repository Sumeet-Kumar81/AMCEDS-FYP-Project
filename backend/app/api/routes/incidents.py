"""Dispatcher incident queue, detail, edit and audio (UC-06, UC-01). 501 stubs until their tasks."""
from fastapi import APIRouter, Depends

from app.api.deps import DISPATCHER
from app.api.errors import ERROR_RESPONSES, NotImplementedYet
from app.schemas.incident import IncidentDetailOut, IncidentSummaryOut

router = APIRouter(prefix="/incidents", tags=["incidents"], responses=ERROR_RESPONSES, dependencies=[Depends(DISPATCHER)])


@router.get("", response_model=list[IncidentSummaryOut])
async def list_incidents():
    """Incident queue, sorted by severity then received time."""
    raise NotImplementedYet("B1-A1-20")


@router.get("/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(incident_id: int):
    raise NotImplementedYet("B1-A1-20")


@router.patch("/{incident_id}", response_model=IncidentDetailOut)
async def edit_incident(incident_id: int):
    """Edit type, severity, victims or location; the recommendation is calculated again."""
    raise NotImplementedYet("B1-A1-21")


@router.get("/{incident_id}/audio")
async def get_incident_audio(incident_id: int):
    raise NotImplementedYet("B1-A1-17")
