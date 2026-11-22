"""Dispatch approval (built, B1-A1-25) and assignment changes (UC-06, UC-09; 501 until B1-A1-26).

Safety rule: vehicles are locked only here, at approval by an authenticated dispatcher; 409 if a
vehicle already has an open assignment or cannot take one.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DISPATCHER, get_db
from app.api.errors import ERROR_RESPONSES, ApiError, NotImplementedYet
from app.schemas.dispatch import DispatchIn
from app.schemas.incident import AssignmentOut
from app.services import dispatch as service
from app.services.auth import Authenticated

router = APIRouter(tags=["dispatch"], responses=ERROR_RESPONSES, dependencies=[Depends(DISPATCHER)])


def _out(a) -> AssignmentOut:
    return AssignmentOut(assignment_id=a.assignment_id, vehicle_id=a.vehicle_id, approved_by=a.approved_by,
                         hospital_id=a.hospital_id, status=a.status, approved_at=a.approved_at)


@router.post("/incidents/{incident_id}/dispatch", status_code=201, response_model=list[AssignmentOut])
async def approve_dispatch(incident_id: int, body: DispatchIn, auth: Authenticated = Depends(DISPATCHER),
                           db: AsyncSession = Depends(get_db)) -> list[AssignmentOut]:
    """Send the chosen vehicles: locks them, creates one approved assignment each (who and when), sets the
    incident to dispatched and audits the AI suggestion next to the dispatcher's choice.
    409 ``vehicle_locked`` / ``vehicle_unavailable`` (with ``next_best``) or ``incident_not_dispatchable``."""
    try:
        assignments = await service.approve(db, incident_id, body, auth.user)
        result = [_out(a) for a in assignments]
        await db.commit()
        return result
    except service.DispatchError as err:
        await db.rollback()
        details = err.details
        if isinstance(details, dict) and details.pop("race", False):
            details["next_best"] = await service.next_best(db, incident_id, set(body.vehicle_ids))
        raise ApiError(err.status, err.message, code=err.code, details=details) from None


@router.patch("/assignments/{assignment_id}/hospital", response_model=AssignmentOut)
async def change_hospital(assignment_id: int):
    raise NotImplementedYet("B1-A1-26")


@router.post("/assignments/{assignment_id}/cancel", response_model=AssignmentOut)
async def cancel_assignment(assignment_id: int):
    raise NotImplementedYet("B1-A1-26")
