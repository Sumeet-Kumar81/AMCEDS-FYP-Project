"""Incident history, performance measures and export (UC-13). 501 stubs until B1-A1-32."""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet

router = APIRouter(prefix="/analytics", tags=["analytics"], responses=ERROR_RESPONSES)


@router.get("/incidents")
async def incident_history():
    raise NotImplementedYet("B1-A1-32")


@router.get("/performance")
async def performance():
    raise NotImplementedYet("B1-A1-32")


@router.get("/export")
async def export():
    """CSV or PDF export."""
    raise NotImplementedYet("B1-A1-32")
