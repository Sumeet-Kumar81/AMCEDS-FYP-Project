from fastapi import APIRouter, HTTPException

from app.schemas.report import ReportIn, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportOut, status_code=201)
async def submit_report(body: ReportIn):
    """UC-01 (Day 3). STUB: validate -> rate limit -> save Incident Record -> return INC-ID.
    Rule: SAVE BEFORE PROCESSING (NFR-P12)."""
    if not body.description:
        raise HTTPException(422, "description or audio is required")
    # TODO Day 3: IntakeService.create(body) -> persist -> pipeline_state='pending'
    return ReportOut(incident_id="INC-000000")
