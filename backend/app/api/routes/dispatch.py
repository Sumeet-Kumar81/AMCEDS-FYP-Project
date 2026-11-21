"""Dispatch approval and assignment changes (UC-06, UC-09). 501 stubs until their tasks.

Safety rule for B1-A1-25: vehicles are locked only here, at approval by an authenticated
dispatcher; 409 if a vehicle already has an open assignment.
"""
from fastapi import APIRouter, Depends

from app.api.deps import DISPATCHER
from app.api.errors import ERROR_RESPONSES, NotImplementedYet
from app.schemas.incident import AssignmentOut

router = APIRouter(tags=["dispatch"], responses=ERROR_RESPONSES, dependencies=[Depends(DISPATCHER)])


@router.post("/incidents/{incident_id}/dispatch", status_code=201, response_model=list[AssignmentOut])
async def approve_dispatch(incident_id: int):
    raise NotImplementedYet("B1-A1-25")


@router.patch("/assignments/{assignment_id}/hospital", response_model=AssignmentOut)
async def change_hospital(assignment_id: int):
    raise NotImplementedYet("B1-A1-26")


@router.post("/assignments/{assignment_id}/cancel", response_model=AssignmentOut)
async def cancel_assignment(assignment_id: int):
    raise NotImplementedYet("B1-A1-26")
