"""Contract C-3: login, tokens, the signed-in user and role names (task B1-A1-04).

Session design follows D-023 (approved 2026-11-21 by the project developer):
  * Access token: short-lived JWT (15 minutes) whose ``jti`` is the session id in ``user_sessions``
    (SDS v1.1 Table 5.14).
  * Refresh token: exchanged at ``POST /api/v1/auth/refresh``. Refresh is refused when the session has
    been idle for more than 30 minutes (NFR-C4), unless the user is a driver with an open assignment
    (UC-11 1b).
  * Logout ends the session (``user_sessions.revoked_at``); its tokens stop working.
Roles are the three in SDS Table 5.4. The password is never returned or echoed.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

ACCESS_TOKEN_MINUTES = 15  # D-023
IDLE_TIMEOUT_MINUTES = 30  # NFR-C4, D-023


class UserRole(StrEnum):
    DISPATCHER = "dispatcher"
    DRIVER = "driver"
    ADMIN = "admin"


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(_Contract):
    username: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=200)


class RefreshIn(_Contract):
    refresh_token: str = Field(min_length=1)


class TokenOut(_Contract):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0, description="Seconds until the access token expires (15 minutes, D-023)")
    refresh_token: str


class MeOut(_Contract):
    """The signed-in user (SDS Table 5.4 without password_hash, failed_login_count or locked_until)."""

    user_id: int
    full_name: str
    username: str
    role: UserRole
    phone: str | None = None
    on_duty: bool = Field(description="Drivers only: true while on duty (GPS shared only then)")


class AccessTokenClaims(_Contract):
    """Claims inside the access JWT. ``jti`` is the ``user_sessions`` session id."""

    sub: str = Field(description="user_id as a string")
    role: UserRole
    jti: str = Field(min_length=1)
    iat: int
    exp: int
    type: Literal["access"] = "access"
