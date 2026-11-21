"""Login, session refresh, logout and the signed-in user (UC-11). Contract C-3; 501 until B1-A1-14."""
from fastapi import APIRouter

from app.api.errors import ERROR_RESPONSES, NotImplementedYet
from app.schemas.auth import LoginIn, MeOut, RefreshIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn):
    raise NotImplementedYet("B1-A1-14")


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn):
    raise NotImplementedYet("B1-A1-14")


@router.post("/logout", status_code=204)
async def logout():
    raise NotImplementedYet("B1-A1-14")


@router.get("/me", response_model=MeOut)
async def me():
    raise NotImplementedYet("B1-A1-14")
