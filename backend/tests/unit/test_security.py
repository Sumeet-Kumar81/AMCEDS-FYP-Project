"""core/security.py unit tests (B1-A1-14): hashing and JWT tokens."""
import time

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.security import ALGORITHM, TokenError, create_token, decode_token, hash_password, verify_password
from app.schemas.auth import UserRole


def test_hash_and_verify() -> None:
    h = hash_password("SIMULATED-pass-123")
    assert h != "SIMULATED-pass-123" and h.startswith("$2")
    assert verify_password("SIMULATED-pass-123", h) and not verify_password("other", h)
    assert not verify_password("x", "not-a-bcrypt-hash")


def test_access_token_round_trip() -> None:
    token, lifetime = create_token(kind="access", user_id=7, session_id="s1", role=UserRole.DRIVER)
    claims = decode_token(token, "access")
    assert (claims.sub, claims.role, claims.jti, claims.type) == ("7", UserRole.DRIVER, "s1", "access")
    assert claims.exp - claims.iat == lifetime == get_settings().jwt_expire_minutes * 60


def test_refresh_token_round_trip_and_lifetime() -> None:
    token, lifetime = create_token(kind="refresh", user_id=7, session_id="s1")
    claims = decode_token(token, "refresh")
    assert claims.type == "refresh" and lifetime == get_settings().jwt_refresh_hours * 3600


def test_access_token_needs_a_role() -> None:
    with pytest.raises(ValueError):
        create_token(kind="access", user_id=1, session_id="s")


@pytest.mark.parametrize("kind,expected", [("access", "refresh"), ("refresh", "access")])
def test_wrong_kind_rejected(kind: str, expected: str) -> None:
    token, _ = create_token(kind=kind, user_id=1, session_id="s", role=UserRole.ADMIN)
    with pytest.raises(TokenError):
        decode_token(token, expected)


def test_expired_rejected() -> None:
    token, _ = create_token(kind="access", user_id=1, session_id="s", role=UserRole.ADMIN, now=int(time.time()) - 10_000)
    with pytest.raises(TokenError):
        decode_token(token, "access")


def test_other_key_and_unsigned_tokens_rejected() -> None:
    claims = {"sub": "1", "jti": "s", "iat": int(time.time()), "exp": int(time.time()) + 60, "type": "access", "role": "admin"}
    with pytest.raises(TokenError):
        decode_token(jwt.encode(claims, "another-secret-that-is-long-enough!!", algorithm=ALGORITHM), "access")
    unsigned = jwt.encode(claims, "", algorithm=ALGORITHM).rsplit(".", 1)[0] + "."
    with pytest.raises(TokenError):
        decode_token(unsigned, "access")


def test_unknown_role_in_token_rejected() -> None:
    claims = {"sub": "1", "jti": "s", "iat": int(time.time()), "exp": int(time.time()) + 60, "type": "access", "role": "root"}
    with pytest.raises(TokenError):
        decode_token(jwt.encode(claims, get_settings().jwt_secret, algorithm=ALGORITHM), "access")
