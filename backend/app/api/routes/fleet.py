"""Vehicle list, live fleet snapshot and hospital list (UC-10, UC-09). 501 stubs until their tasks."""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet

router = APIRouter(tags=["fleet"], responses=ERROR_RESPONSES)


@router.get("/vehicles")
async def list_vehicles():
    raise NotImplementedYet("B1-A1-25")


@router.get("/fleet/live")
async def fleet_live():
    raise NotImplementedYet("B1-A1-27")


@router.get("/hospitals")
async def list_hospitals():
    raise NotImplementedYet("B1-A1-26")
