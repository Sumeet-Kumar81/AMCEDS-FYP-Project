"""Public report intake (UC-01). ``POST /api/v1/reports`` is real since B1-A1-16; voice and caller
confirmation are 501 stubs until B1-A1-17 and B1-A1-24.

Safety rule 1 (NFR-P12): the answer is sent only after the record is committed. If saving fails the
caller gets 503 and never a reference number.
"""
import logging

from fastapi import APIRouter, Depends, File, Path, Response, UploadFile
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.errors import ERROR_RESPONSES, ApiError, ErrorBody, NotImplementedYet
from app.schemas.incident import REFERENCE_NO_PATTERN
from app.schemas.report import ReportAcceptedOut, ReportIn
from app.services import intake

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"], responses=ERROR_RESPONSES)

NOT_SAVED = ("Your report could not be saved. Please try again. If life is in danger, also call 1122.")


def _accepted(incident) -> ReportAcceptedOut:
    return ReportAcceptedOut(reference_no=incident.reference_no, status=incident.status, received_at=incident.received_at)


async def _safe_rollback(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except (SQLAlchemyError, OSError):  # the database may be gone; the request is failing anyway
        logger.exception("rollback after a failed report save also failed")


@router.post(
    "",
    status_code=201,
    response_model=ReportAcceptedOut,
    responses={200: {"model": ReportAcceptedOut, "description": "Resend: the report was already saved"},
               503: {"model": ErrorBody, "description": "Not saved; no reference number"}},
)
async def submit_report(body: ReportIn, response: Response, db: AsyncSession = Depends(get_db)) -> ReportAcceptedOut:
    """Save a text report from the web page or the app and return its reference number."""
    try:
        incident, created = await intake.create_report(db, body)
        await db.commit()
    except IntegrityError:
        await _safe_rollback(db)
        if body.client_request_id:  # the same report arrived twice at the same moment
            existing = await intake.find_by_client_request_id(db, body.client_request_id)
            if existing is not None:
                response.status_code = 200
                return _accepted(existing)
        logger.exception("report not saved (integrity error)")
        raise ApiError(503, NOT_SAVED, code="service_unavailable") from None
    except (SQLAlchemyError, OSError):
        await _safe_rollback(db)
        logger.exception("report not saved (database unavailable)")
        raise ApiError(503, NOT_SAVED, code="service_unavailable") from None
    if not created:
        response.status_code = 200
    logger.info("report saved %s", incident.reference_no)
    return _accepted(incident)


@router.post("/voice", status_code=201)
async def submit_voice_report(audio: UploadFile = File(...)):
    """Submit a voice report (WAV, MP3 or M4A, up to 2 minutes)."""
    raise NotImplementedYet("B1-A1-17")


@router.post("/{reference_no}/confirmation")
async def confirm_report(reference_no: str = Path(pattern=REFERENCE_NO_PATTERN)):
    """The caller confirms or denies the report (with the code sent to them)."""
    raise NotImplementedYet("B1-A1-24")
