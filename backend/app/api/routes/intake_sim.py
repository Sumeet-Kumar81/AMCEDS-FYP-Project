"""SIMULATED SMS and voice gateway webhooks (UC-01, D-014). 501 stubs until Batch 4."""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet

router = APIRouter(prefix="/intake", tags=["intake (simulator)"], responses=ERROR_RESPONSES)


@router.post("/sms")
async def intake_sms():
    raise NotImplementedYet("B4-01")


@router.post("/voice")
async def intake_voice():
    raise NotImplementedYet("B4-02")
