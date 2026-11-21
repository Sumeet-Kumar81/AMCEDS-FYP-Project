"""Contract C-3 tests (B1-A1-04): auth shapes and roles (session design D-023)."""
import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    ACCESS_TOKEN_MINUTES,
    IDLE_TIMEOUT_MINUTES,
    AccessTokenClaims,
    LoginIn,
    MeOut,
    RefreshIn,
    TokenOut,
    UserRole,
)


def test_roles_match_sds_table_5_4() -> None:
    assert [r.value for r in UserRole] == ["dispatcher", "driver", "admin"]


def test_session_timings_follow_d023() -> None:
    assert ACCESS_TOKEN_MINUTES == 15 and IDLE_TIMEOUT_MINUTES == 30


def test_login_hides_the_password() -> None:
    body = LoginIn(username="dispatcher1", password="SIMULATED-pass")
    assert body.password.get_secret_value() == "SIMULATED-pass"
    assert "SIMULATED-pass" not in repr(body) and "SIMULATED-pass" not in str(body.model_dump())


@pytest.mark.parametrize("data", [
    {"username": "", "password": "x"},
    {"username": "u", "password": ""},
    {"username": "u"},
    {"username": "u", "password": "x", "role": "admin"},
])
def test_invalid_login_bodies(data: dict) -> None:
    with pytest.raises(ValidationError):
        LoginIn.model_validate(data)


def test_token_out_shape() -> None:
    t = TokenOut(access_token="a", expires_in=900, refresh_token="r")
    assert t.token_type == "bearer"
    for bad in ({"expires_in": 0}, {"token_type": "mac"}, {"extra": 1}):
        with pytest.raises(ValidationError):
            TokenOut.model_validate({"access_token": "a", "expires_in": 900, "refresh_token": "r", **bad})


def test_refresh_needs_a_token() -> None:
    with pytest.raises(ValidationError):
        RefreshIn(refresh_token="")


def test_me_never_carries_password_or_lock_fields() -> None:
    assert not {"password", "password_hash", "failed_login_count", "locked_until"} & set(MeOut.model_fields)
    me = MeOut(user_id=1, full_name="SIMULATED Driver", username="driver1", role="driver", on_duty=True)
    assert me.role is UserRole.DRIVER
    with pytest.raises(ValidationError):
        MeOut.model_validate({**me.model_dump(), "role": "superuser"})


def test_access_token_claims() -> None:
    c = AccessTokenClaims(sub="7", role="dispatcher", jti="session-1", iat=1, exp=901)
    assert c.type == "access"
    for bad in ({"jti": ""}, {"type": "refresh"}, {"role": "root"}):
        with pytest.raises(ValidationError):
            AccessTokenClaims.model_validate({**c.model_dump(), **bad})
