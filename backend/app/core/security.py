"""Password hashing and JWT tokens (B1-A1-14, session design D-023).

* Passwords: bcrypt. The real password is never stored or logged.
* Tokens: HS256 only (the algorithm list is fixed, so a token cannot choose its own algorithm).
  Access tokens live ``jwt_expire_minutes`` (15, D-023); refresh tokens ``jwt_refresh_hours`` (12).
  Both carry the session id as ``jti``; the session row decides whether they still work.
"""
from __future__ import annotations

import secrets
import time
from functools import lru_cache
from typing import Literal

import bcrypt
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.auth import AccessTokenClaims, RefreshTokenClaims, UserRole

ALGORITHM = "HS256"
TokenKind = Literal["access", "refresh"]


class TokenError(Exception):
    """The token is malformed, signed with another key, of the wrong kind or expired."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):  # not a bcrypt hash
        return False


@lru_cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def spend_password_check_time(password: str) -> None:
    """Run one bcrypt check for an unknown or disabled user, so the answer takes as long as for a
    real account and usernames cannot be guessed from the timing."""
    verify_password(password, _dummy_hash())


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def create_token(*, kind: TokenKind, user_id: int, session_id: str, role: UserRole | None = None,
                 now: int | None = None) -> tuple[str, int]:
    """Return ``(token, seconds_until_expiry)``."""
    settings = get_settings()
    issued = int(now if now is not None else time.time())
    lifetime = settings.jwt_expire_minutes * 60 if kind == "access" else settings.jwt_refresh_hours * 3600
    claims: dict[str, object] = {"sub": str(user_id), "jti": session_id, "iat": issued, "exp": issued + lifetime, "type": kind}
    if kind == "access":
        if role is None:
            raise ValueError("an access token needs a role")
        claims["role"] = UserRole(role).value
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM), lifetime


def decode_token(token: str, kind: TokenKind) -> AccessTokenClaims | RefreshTokenClaims:
    try:
        raw = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:  # includes expired tokens and bad signatures
        raise TokenError(str(exc)) from None
    if raw.get("type") != kind:
        raise TokenError(f"expected a {kind} token")
    try:
        return AccessTokenClaims.model_validate(raw) if kind == "access" else RefreshTokenClaims.model_validate(raw)
    except ValidationError as exc:
        raise TokenError("token claims are not valid") from exc
