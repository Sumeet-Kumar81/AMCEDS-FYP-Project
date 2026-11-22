"""Driver app: duty and GPS (UC-11; 501 until B1-A1-27) and the assignment lifecycle (UC-08, UC-09; built
in B1-A1-26). A driver may act only on the assignments of the vehicle they drive (403 otherwise, TC-48).

Safety rule for B1-A1-27: GPS points are accepted only while the driver is on duty.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DRIVER, get_db, require_driver_owns_assignment
from app.api.errors import ERROR_RESPONSES, ApiError, NotImplementedYet
from app.models import Assignment
from app.schemas.assignment import DriverAssignmentOut
from app.schemas.dispatch import DeclineIn, TripStatusIn
from app.schemas.incident import AssignmentOut
from app.services import assignments as service
from app.services.auth import Authenticated

router = APIRouter(prefix="/driver", tags=["driver"], responses=ERROR_RESPONSES, dependencies=[Depends(DRIVER)])


@router.post("/duty/start")
async def start_duty():
    raise NotImplementedYet("B1-A1-27")


@router.post("/duty/end")
async def end_duty():
    raise NotImplementedYet("B1-A1-27")


def assignment_out(a: Assignment) -> AssignmentOut:
    return AssignmentOut(
        assignment_id=a.assignment_id, vehicle_id=a.vehicle_id, approved_by=a.approved_by, hospital_id=a.hospital_id,
        status=a.status, approved_at=a.approved_at, accepted_at=a.accepted_at, on_scene_at=a.on_scene_at,
        picked_up_at=a.picked_up_at, at_hospital_at=a.at_hospital_at, completed_at=a.completed_at,
        notified_at=a.notified_at, decline_reason=a.decline_reason, declined_at=a.declined_at, timed_out_at=a.timed_out_at)


async def run(db: AsyncSession, action) -> AssignmentOut:
    """Run one lifecycle change in its own transaction; a refusal changes nothing."""
    try:
        out = assignment_out(await action)
        await db.commit()
        return out
    except service.AssignmentError as err:
        await db.rollback()
        raise ApiError(err.status, err.message, code=err.code, details=err.details) from None


@router.get("/assignments/current", response_model=DriverAssignmentOut,
            responses={204: {"description": "No open assignment"}})
async def current_assignment(auth: Authenticated = Depends(DRIVER), db: AsyncSession = Depends(get_db)):
    """The open assignment of the vehicle this driver drives (UC-08 step 1), or 204 when there is none."""
    out = await service.current(db, auth.user)
    return out if out is not None else Response(status_code=204)


@router.post("/assignments/{assignment_id}/accept", response_model=AssignmentOut)
async def accept_assignment(assignment_id: int, auth: Authenticated = Depends(require_driver_owns_assignment),
                            db: AsyncSession = Depends(get_db)) -> AssignmentOut:
    """approved → accepted; the vehicle is en route. 409 if not on duty or not approved."""
    return await run(db, service.accept(db, assignment_id, auth.user))


@router.post("/assignments/{assignment_id}/decline", response_model=AssignmentOut)
async def decline_assignment(assignment_id: int, body: DeclineIn, auth: Authenticated = Depends(require_driver_owns_assignment),
                             db: AsyncSession = Depends(get_db)) -> AssignmentOut:
    """"Cannot go" with a reason from the list: the vehicle is free again and the dispatcher must send another."""
    return await run(db, service.decline(db, assignment_id, auth.user, body.reason))


@router.post("/assignments/{assignment_id}/status", response_model=AssignmentOut)
async def trip_status(assignment_id: int, body: TripStatusIn, auth: Authenticated = Depends(require_driver_owns_assignment),
                      db: AsyncSession = Depends(get_db)) -> AssignmentOut:
    """On scene, picked up, at hospital, available (= trip completed, vehicle free) — in that order (C-7)."""
    return await run(db, service.trip_status(db, assignment_id, auth.user, body.status))


@router.post("/locations")
async def post_locations():
    """GPS points, also sent in batches after a network drop."""
    raise NotImplementedYet("B1-A1-27")
