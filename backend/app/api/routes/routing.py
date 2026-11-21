"""Route proxy for the driver app and dashboard (UC-08). OSRM itself is never public (CI-6). 501 stub."""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet

router = APIRouter(prefix="/routing", tags=["routing"], responses=ERROR_RESPONSES)


@router.get("/route")
async def route():
    raise NotImplementedYet("B1-A2-15")
