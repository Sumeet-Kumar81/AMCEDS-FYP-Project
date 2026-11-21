"""Driver app: duty, current assignment, accept/decline, trip status and GPS (UC-08, UC-09, UC-11). 501 stubs.

Safety rule for B1-A1-27: GPS points are accepted only while the driver is on duty.
"""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet

router = APIRouter(prefix="/driver", tags=["driver"], responses=ERROR_RESPONSES)


@router.post("/duty/start")
async def start_duty():
    raise NotImplementedYet("B1-A1-27")


@router.post("/duty/end")
async def end_duty():
    raise NotImplementedYet("B1-A1-27")


@router.get("/assignments/current")
async def current_assignment():
    raise NotImplementedYet("B1-A1-26")


@router.post("/assignments/{assignment_id}/accept")
async def accept_assignment(assignment_id: int):
    raise NotImplementedYet("B1-A1-26")


@router.post("/assignments/{assignment_id}/decline")
async def decline_assignment(assignment_id: int):
    raise NotImplementedYet("B1-A1-26")


@router.post("/assignments/{assignment_id}/status")
async def trip_status(assignment_id: int):
    """On scene, picked up, at hospital, available."""
    raise NotImplementedYet("B1-A1-26")


@router.post("/locations")
async def post_locations():
    """GPS points, also sent in batches after a network drop."""
    raise NotImplementedYet("B1-A1-27")
