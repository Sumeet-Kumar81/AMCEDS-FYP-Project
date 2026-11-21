"""Request dependencies: database session, signed-in user, role checks (B1-A1-15).

* ``current_user``: 401 without a valid access token or when the session has ended or idled out.
  The role used for checks is read from the database on every request, not trusted from the token,
  so a changed or disabled account takes effect at once.
* ``require_roles(...)``: 403 when the signed-in user has another role.
* ``require_driver_owns_assignment``: a driver may act only on assignments of the vehicle they drive
  (TC-48); another driver's assignment is 403, a missing one 404.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.db import SessionLocal
from app.models import Assignment, Vehicle
from app.schemas.auth import UserRole
from app.services.auth import Authenticated, AuthError, authenticate

bearer = HTTPBearer(auto_error=False, description="Access token from POST /api/v1/auth/login")
NOT_SIGNED_IN = {"WWW-Authenticate": "Bearer"}


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Authenticated:
    if credentials is None:
        raise ApiError(401, "Not signed in.", code="unauthorized", headers=NOT_SIGNED_IN)
    try:
        auth = await authenticate(db, credentials.credentials)
    except AuthError as exc:
        await db.commit()  # keep an idle session's end and its audit row
        raise ApiError(exc.status_code, exc.message, code=exc.code, headers=NOT_SIGNED_IN) from None
    await db.commit()  # record the activity (last_activity_at)
    return auth


def require_roles(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, Authenticated]]:
    allowed = frozenset(UserRole(r) for r in roles)

    async def checker(auth: Authenticated = Depends(current_user)) -> Authenticated:
        if UserRole(auth.user.role) not in allowed:
            raise ApiError(403, "Your role may not do this.", code="forbidden")
        return auth

    checker.__name__ = "require_" + "_or_".join(sorted(r.value for r in allowed))
    return checker


ANY_STAFF = require_roles(UserRole.DISPATCHER, UserRole.DRIVER, UserRole.ADMIN)
DISPATCHER = require_roles(UserRole.DISPATCHER)
DRIVER = require_roles(UserRole.DRIVER)
ADMIN = require_roles(UserRole.ADMIN)
DISPATCHER_OR_ADMIN = require_roles(UserRole.DISPATCHER, UserRole.ADMIN)
DISPATCHER_OR_DRIVER = require_roles(UserRole.DISPATCHER, UserRole.DRIVER)


async def require_driver_owns_assignment(
    assignment_id: int,
    auth: Authenticated = Depends(DRIVER),
    db: AsyncSession = Depends(get_db),
) -> Authenticated:
    row = (await db.execute(
        select(Assignment.assignment_id, Vehicle.driver_id)
        .join(Vehicle, Vehicle.vehicle_id == Assignment.vehicle_id)
        .where(Assignment.assignment_id == assignment_id)
    )).first()
    if row is None:
        raise ApiError(404, "No such assignment.", code="not_found")
    if row.driver_id != auth.user.user_id:
        raise ApiError(403, "This assignment belongs to another vehicle.", code="forbidden")
    return auth
