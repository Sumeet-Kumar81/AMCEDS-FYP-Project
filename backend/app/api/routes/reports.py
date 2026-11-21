"""Public report intake (UC-01). Contract C-4; every endpoint here is a 501 stub until its task.

``POST /api/v1/reports`` used to return a hard-coded ``INC-000000`` without saving anything. That
broke the safety rule "never return a reference number for a report that was not saved" (NFR-P12),
so it now validates the input and returns 501 until B1-A1-16 saves the record for real.
"""
from fastapi import APIRouter, File, HTTPException, Path, UploadFile

from app.api.errors import ERROR_RESPONSES, NotImplementedYet
from app.schemas.incident import REFERENCE_NO_PATTERN
from app.schemas.report import ReportIn

router = APIRouter(prefix="/reports", tags=["reports"], responses=ERROR_RESPONSES)


@router.post("", status_code=201)
async def submit_report(body: ReportIn):
    """Submit a text report. Will save the Incident Record first and return ``reference_no`` (B1-A1-16)."""
    if not (body.description and body.description.strip()):
        raise HTTPException(422, "description or audio is required")
    raise NotImplementedYet("B1-A1-16")


@router.post("/voice", status_code=201)
async def submit_voice_report(audio: UploadFile = File(...)):
    """Submit a voice report (WAV, MP3 or M4A, up to 2 minutes)."""
    raise NotImplementedYet("B1-A1-17")


@router.post("/{reference_no}/confirmation")
async def confirm_report(reference_no: str = Path(pattern=REFERENCE_NO_PATTERN)):
    """The caller confirms or denies the report (with the code sent to them)."""
    raise NotImplementedYet("B1-A1-24")
