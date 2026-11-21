"""Authentication service (B1-A1-14; SRS UC-11, NFR-C4; session design D-023).

* ``login``: disabled accounts refused; after ``lockout_attempts`` wrong passwords the account is
  locked for ``lockout_min`` minutes and even the right password is refused (TC-32); success resets
  the counter and opens a ``user_sessions`` row. Unknown user, disabled user and wrong password give
  the same answer and take about the same time.
* ``refresh``: refused once the session has been idle longer than ``idle_logout_min``, unless the
  user is a driver with an open assignment (UC-11 1b). An idle session is ended.
* ``logout``: ends the session; its access and refresh tokens stop working.
* ``authenticate``: used on every private request; checks token, session and account, then records
  the activity.

The functions change rows and write audit entries but never commit. On ``AuthError`` the caller
must still commit, so a failed attempt (counter, lock, audit row) is kept.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    new_session_id,
    spend_password_check_time,
    verify_password,
)
from app.models import Assignment, User, UserSession, Vehicle
from app.schemas.assignment import OPEN_ASSIGNMENT_STATUSES
from app.schemas.auth import TokenOut, UserRole
from app.services.audit import AuditAction, record
from app.services.settings import get_value

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid username or password."


class AuthError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


def _invalid() -> AuthError:
    return AuthError(401, "invalid_credentials", INVALID_CREDENTIALS)


def _session_ended() -> AuthError:
    return AuthError(401, "session_ended", "Your session has ended. Please sign in again.")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Authenticated:
    user: User
    session: UserSession


def _tokens(user: User, session_id: str) -> TokenOut:
    access, expires_in = create_token(kind="access", user_id=user.user_id, session_id=session_id, role=UserRole(user.role))
    refresh, _ = create_token(kind="refresh", user_id=user.user_id, session_id=session_id)
    return TokenOut(access_token=access, expires_in=expires_in, refresh_token=refresh)


async def driver_has_open_assignment(db: AsyncSession, user_id: int) -> bool:
    return bool(await db.scalar(select(exists().where(
        Assignment.vehicle_id == Vehicle.vehicle_id,
        Vehicle.driver_id == user_id,
        Assignment.status.in_([s.value for s in OPEN_ASSIGNMENT_STATUSES]),
    ))))


async def _is_idle(db: AsyncSession, user: User, user_session: UserSession, now: datetime) -> bool:
    idle_limit = timedelta(minutes=int(await get_value(db, "idle_logout_min")))
    if now - user_session.last_activity_at <= idle_limit:
        return False
    if user.role == UserRole.DRIVER.value and await driver_has_open_assignment(db, user.user_id):
        return False  # UC-11 1b: a driver on a job stays signed in
    return True


async def login(db: AsyncSession, username: str, password: str, *, now: datetime | None = None) -> TokenOut:
    now = now or utcnow()
    user = await db.scalar(select(User).where(User.username == username).with_for_update())
    if user is None or not user.is_active:
        spend_password_check_time(password)
        await record(db, AuditAction.AUTH_LOGIN_FAILED, user_id=user.user_id if user else None,
                     details={"username": username, "reason": "unknown_user" if user is None else "disabled"})
        raise _invalid()

    if user.locked_until is not None and user.locked_until > now:
        spend_password_check_time(password)
        await record(db, AuditAction.AUTH_LOGIN_FAILED, user_id=user.user_id, details={"reason": "locked"})
        raise _locked(user.locked_until, now)

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        attempts = int(await get_value(db, "lockout_attempts"))
        if user.failed_login_count >= attempts:
            user.locked_until = now + timedelta(minutes=int(await get_value(db, "lockout_min")))
            user.failed_login_count = 0
            await record(db, AuditAction.AUTH_LOCKED, user_id=user.user_id,
                         details={"attempts": attempts, "locked_until": user.locked_until.isoformat()})
            raise _locked(user.locked_until, now)
        await record(db, AuditAction.AUTH_LOGIN_FAILED, user_id=user.user_id,
                     details={"reason": "wrong_password", "failed_login_count": user.failed_login_count})
        raise _invalid()

    user.failed_login_count = 0
    user.locked_until = None
    user_session = UserSession(session_id=new_session_id(), user_id=user.user_id, created_at=now, last_activity_at=now)
    db.add(user_session)
    await db.flush()
    await record(db, AuditAction.AUTH_LOGIN, user_id=user.user_id, details={"session_id": user_session.session_id})
    return _tokens(user, user_session.session_id)


def _locked(until: datetime, now: datetime) -> AuthError:
    minutes = max(1, int((until - now).total_seconds() + 59) // 60)
    return AuthError(401, "account_locked", f"Too many wrong passwords. The account is locked; try again in {minutes} minute(s).")


async def _load_session(db: AsyncSession, session_id: str) -> tuple[User, UserSession]:
    row = (await db.execute(
        select(User, UserSession).join(UserSession, UserSession.user_id == User.user_id)
        .where(UserSession.session_id == session_id).with_for_update(of=UserSession)
    )).first()
    if row is None:
        raise _session_ended()
    user, user_session = row
    if user_session.revoked_at is not None or not user.is_active:
        raise _session_ended()
    return user, user_session


async def refresh(db: AsyncSession, refresh_token: str, *, now: datetime | None = None) -> TokenOut:
    now = now or utcnow()
    try:
        claims = decode_token(refresh_token, "refresh")
    except TokenError:
        raise _session_ended() from None
    user, user_session = await _load_session(db, claims.jti)
    if str(user.user_id) != claims.sub:
        raise _session_ended()
    if await _is_idle(db, user, user_session, now):
        user_session.revoked_at = now
        await record(db, AuditAction.AUTH_LOGOUT, user_id=user.user_id,
                     details={"session_id": user_session.session_id, "reason": "idle"})
        raise _session_ended()
    user_session.last_activity_at = now
    return _tokens(user, user_session.session_id)


async def authenticate(db: AsyncSession, access_token: str, *, now: datetime | None = None) -> Authenticated:
    """Check an access token on a private request and record the activity."""
    now = now or utcnow()
    try:
        claims = decode_token(access_token, "access")
    except TokenError:
        raise _session_ended() from None
    user, user_session = await _load_session(db, claims.jti)
    if str(user.user_id) != claims.sub:
        raise _session_ended()
    if await _is_idle(db, user, user_session, now):
        user_session.revoked_at = now
        await record(db, AuditAction.AUTH_LOGOUT, user_id=user.user_id,
                     details={"session_id": user_session.session_id, "reason": "idle"})
        raise _session_ended()
    user_session.last_activity_at = now
    return Authenticated(user=user, session=user_session)


async def logout(db: AsyncSession, current: Authenticated, *, now: datetime | None = None) -> None:
    current.session.revoked_at = now or utcnow()
    await record(db, AuditAction.AUTH_LOGOUT, user_id=current.user.user_id,
                 details={"session_id": current.session.session_id, "reason": "logout"})
