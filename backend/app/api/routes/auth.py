"""Login, session refresh, logout and the signed-in user (UC-11). Contract C-3; built in B1-A1-14."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ANY_STAFF, get_db
from app.api.errors import ERROR_RESPONSES, ApiError
from app.schemas.auth import LoginIn, MeOut, RefreshIn, TokenOut, UserRole
from app.services import auth as auth_service
from app.services.auth import Authenticated, AuthError

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)


async def _commit_then_raise(db: AsyncSession, exc: AuthError) -> None:
    await db.commit()  # keep the failed attempt: counter, lock and audit row
    raise ApiError(exc.status_code, exc.message, code=exc.code, headers={"WWW-Authenticate": "Bearer"}) from None


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    try:
        tokens = await auth_service.login(db, body.username, body.password.get_secret_value())
    except AuthError as exc:
        await _commit_then_raise(db, exc)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    try:
        tokens = await auth_service.refresh(db, body.refresh_token)
    except AuthError as exc:
        await _commit_then_raise(db, exc)
    await db.commit()
    return tokens


@router.post("/logout", status_code=204, response_class=Response)
async def logout(auth: Authenticated = Depends(ANY_STAFF), db: AsyncSession = Depends(get_db)) -> Response:
    await auth_service.logout(db, auth)
    await db.commit()
    return Response(status_code=204)


@router.get("/me", response_model=MeOut)
async def me(auth: Authenticated = Depends(ANY_STAFF)) -> MeOut:
    u = auth.user
    return MeOut(user_id=u.user_id, full_name=u.full_name, username=u.username, role=UserRole(u.role),
                 phone=u.phone, on_duty=u.on_duty)
