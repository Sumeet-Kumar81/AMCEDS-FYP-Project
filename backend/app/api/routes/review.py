"""Duplicate decisions, review queue, caller confirmation and review decisions (UC-04, UC-07). 501 stubs."""
from fastapi import APIRouter, Depends

from app.api.deps import DISPATCHER
from app.api.errors import ERROR_RESPONSES, NotImplementedYet
from app.schemas.incident import IncidentSummaryOut

router = APIRouter(tags=["review"], responses=ERROR_RESPONSES, dependencies=[Depends(DISPATCHER)])


@router.post("/duplicate-candidates/{candidate_id}/confirm")
async def confirm_duplicate(candidate_id: int):
    raise NotImplementedYet("B1-A1-22")


@router.post("/duplicate-candidates/{candidate_id}/reject")
async def reject_duplicate(candidate_id: int):
    raise NotImplementedYet("B1-A1-22")


@router.get("/review-queue", response_model=list[IncidentSummaryOut])
async def review_queue():
    """Doubtful reports, each with its review reasons."""
    raise NotImplementedYet("B1-A1-23")


@router.post("/incidents/{incident_id}/confirmation-requests")
async def request_caller_confirmation(incident_id: int):
    raise NotImplementedYet("B1-A1-24")


@router.post("/incidents/{incident_id}/review-decision")
async def review_decision(incident_id: int):
    """Real, Fake or Need more information."""
    raise NotImplementedYet("B1-A1-23")
