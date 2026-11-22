"""Vehicle list (built, B1-A1-25), live fleet snapshot and hospital list (UC-10, UC-09; 501 until their tasks)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DISPATCHER, DISPATCHER_OR_DRIVER, get_db
from app.api.errors import ERROR_RESPONSES, NotImplementedYet
from app.schemas.dispatch import VehicleOut
from app.schemas.enums import VehicleType
from app.services import dispatch as dispatch_service

router = APIRouter(tags=["fleet"], responses=ERROR_RESPONSES)


@router.get("/vehicles", dependencies=[Depends(DISPATCHER)], response_model=list[VehicleOut])
async def list_vehicles(
    incident_id: int | None = Query(None, ge=1, description="Sort by straight-line distance to this incident"),
    type: list[VehicleType] | None = Query(None, description="Only these vehicle types (repeat the parameter)"),
    available_only: bool = Query(False, description="Only vehicles that can be dispatched now"),
    db: AsyncSession = Depends(get_db),
) -> list[VehicleOut]:
    """Every vehicle with its driver, duty, last GPS and whether it can take an assignment now (manual
    dispatch, "pick another vehicle"). With ``incident_id``: dispatchable first, then nearest. Read-only."""
    return await dispatch_service.list_vehicles(db, incident_id=incident_id, types=type, available_only=available_only)


@router.get("/fleet/live", dependencies=[Depends(DISPATCHER)])
async def fleet_live():
    raise NotImplementedYet("B1-A1-27")


@router.get("/hospitals", dependencies=[Depends(DISPATCHER_OR_DRIVER)])
async def list_hospitals():
    raise NotImplementedYet("B1-A1-26")
