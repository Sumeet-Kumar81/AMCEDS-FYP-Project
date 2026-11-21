"""Authentication tests (B1-A1-14): TC-32 lockout, D-023 sessions, logout, refresh, disabled users."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import create_token
from app.models import AuditLog, User, UserSession
from app.schemas.auth import UserRole
from app.services.auth import INVALID_CREDENTIALS
from tests.api.conftest import PASSWORD

pytestmark = pytest.mark.db


async def login(api: httpx.AsyncClient, username: str, password: str = PASSWORD) -> httpx.Response:
    return await api.post("/api/v1/auth/login", json={"username": username, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def audits(db: AsyncSession, action: str) -> int:
    return await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == action))


# ---------------------------------------------------------------- login
async def test_login_returns_tokens_and_opens_an_audited_session(api, make_user, db_session) -> None:
    user = await make_user(UserRole.DISPATCHER, "dispatcher_login")
    r = await login(api, "dispatcher_login")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["refresh_token"]
    assert body["expires_in"] == get_settings().jwt_expire_minutes * 60
    assert await db_session.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == user.user_id)) == 1
    assert await audits(db_session, "auth.login") == 1


async def test_unknown_user_wrong_password_and_disabled_user_look_the_same(api, make_user) -> None:
    await make_user(UserRole.DRIVER, "driver_real")
    await make_user(UserRole.DRIVER, "driver_disabled", is_active=False)
    answers = [await login(api, "nobody_here"), await login(api, "driver_real", "wrong-password"),
               await login(api, "driver_disabled")]
    assert {r.status_code for r in answers} == {401}
    assert {r.json()["message"] for r in answers} == {INVALID_CREDENTIALS}
    assert {r.json()["code"] for r in answers} == {"invalid_credentials"}


async def test_tc32_five_wrong_passwords_lock_the_account(api, make_user, db_session) -> None:
    user = await make_user(UserRole.DISPATCHER, "dispatcher_lock")
    for _ in range(4):
        assert (await login(api, "dispatcher_lock", "wrong-password")).json()["code"] == "invalid_credentials"
    fifth = await login(api, "dispatcher_lock", "wrong-password")
    assert fifth.status_code == 401 and fifth.json()["code"] == "account_locked"
    correct = await login(api, "dispatcher_lock")  # the right password is refused while locked
    assert correct.status_code == 401 and correct.json()["code"] == "account_locked" and "15 minute" in correct.json()["message"]
    await db_session.refresh(user)
    assert user.locked_until is not None and user.locked_until > datetime.now(timezone.utc) + timedelta(minutes=14)
    assert await audits(db_session, "auth.locked") == 1


async def test_after_the_lock_expires_the_right_password_works_and_resets_the_counter(api, make_user, db_session) -> None:
    user = await make_user(UserRole.DISPATCHER, "dispatcher_unlock")
    for _ in range(3):
        await login(api, "dispatcher_unlock", "wrong-password")
    await db_session.refresh(user)
    assert user.failed_login_count == 3
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()
    assert (await login(api, "dispatcher_unlock")).status_code == 200
    await db_session.refresh(user)
    assert (user.failed_login_count, user.locked_until) == (0, None)


async def test_the_password_is_never_echoed(api) -> None:
    r = await api.post("/api/v1/auth/login", json={"username": "", "password": "SIMULATED-secret-xyz"})
    assert r.status_code == 422 and "SIMULATED-secret-xyz" not in r.text


# ---------------------------------------------------------------- me, logout, refresh
async def test_me_shows_the_signed_in_user_without_secrets(api, make_user) -> None:
    await make_user(UserRole.DRIVER, "driver_me")
    token = (await login(api, "driver_me")).json()["access_token"]
    r = await api.get("/api/v1/auth/me", headers=bearer(token))
    assert r.status_code == 200 and r.json()["username"] == "driver_me" and r.json()["role"] == "driver"
    assert "password" not in r.text and "password_hash" not in r.text


async def test_logout_ends_the_session(api, make_user, db_session) -> None:
    await make_user(UserRole.ADMIN, "admin_logout")
    tokens = (await login(api, "admin_logout")).json()
    assert (await api.post("/api/v1/auth/logout", headers=bearer(tokens["access_token"]))).status_code == 204
    after = await api.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))
    assert after.status_code == 401 and after.json()["code"] == "session_ended"
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401
    assert await audits(db_session, "auth.logout") == 1


async def test_refresh_gives_new_tokens_for_the_same_session(api, make_user) -> None:
    await make_user(UserRole.DISPATCHER, "dispatcher_refresh")
    tokens = (await login(api, "dispatcher_refresh")).json()
    r = await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert (await api.get("/api/v1/auth/me", headers=bearer(r.json()["access_token"]))).status_code == 200


async def test_tokens_cannot_be_used_as_the_other_kind(api, make_user) -> None:
    await make_user(UserRole.DISPATCHER, "dispatcher_kinds")
    tokens = (await login(api, "dispatcher_kinds")).json()
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})).status_code == 401
    assert (await api.get("/api/v1/auth/me", headers=bearer(tokens["refresh_token"]))).status_code == 401


@pytest.mark.parametrize("token", ["not-a-jwt", "a.b.c"])
async def test_garbage_tokens_are_401(api, token: str) -> None:
    assert (await api.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401


async def test_expired_access_token_is_401(api, make_user, db_session) -> None:
    user = await make_user(UserRole.DISPATCHER)
    session = UserSession(session_id="expired-session", user_id=user.user_id)
    db_session.add(session)
    await db_session.flush()
    old, _ = create_token(kind="access", user_id=user.user_id, session_id="expired-session", role=UserRole.DISPATCHER,
                          now=int(datetime.now(timezone.utc).timestamp()) - 3600)
    assert (await api.get("/api/v1/auth/me", headers=bearer(old))).status_code == 401


# ---------------------------------------------------------------- idle timeout (NFR-C4, D-023)
async def _go_idle(db: AsyncSession, username: str, minutes: int = 31) -> None:
    user_id = await db.scalar(select(User.user_id).where(User.username == username))
    for s in (await db.scalars(select(UserSession).where(UserSession.user_id == user_id))).all():
        s.last_activity_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    await db.flush()


async def test_idle_31_minutes_ends_the_session(api, make_user, db_session) -> None:
    await make_user(UserRole.DISPATCHER, "dispatcher_idle")
    tokens = (await login(api, "dispatcher_idle")).json()
    await _go_idle(db_session, "dispatcher_idle")
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401
    assert (await api.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))).status_code == 401


async def test_idle_29_minutes_is_still_signed_in(api, make_user, db_session) -> None:
    await make_user(UserRole.DISPATCHER, "dispatcher_active")
    tokens = (await login(api, "dispatcher_active")).json()
    await _go_idle(db_session, "dispatcher_active", minutes=29)
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 200


async def test_driver_with_an_open_assignment_stays_signed_in(api, make_user, driver_assignment, db_session) -> None:
    """UC-11 1b."""
    driver = await make_user(UserRole.DRIVER, "driver_on_job")
    await driver_assignment(driver)
    tokens = (await login(api, "driver_on_job")).json()
    await _go_idle(db_session, "driver_on_job", minutes=90)
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 200
    assert (await api.get("/api/v1/auth/me", headers=bearer(tokens["access_token"]))).status_code == 200


async def test_driver_without_an_open_assignment_is_not_exempt(api, make_user, db_session) -> None:
    await make_user(UserRole.DRIVER, "driver_off_job")
    tokens = (await login(api, "driver_off_job")).json()
    await _go_idle(db_session, "driver_off_job")
    assert (await api.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 401


async def test_disabling_a_user_ends_their_sessions(api, make_user, db_session) -> None:
    user = await make_user(UserRole.DISPATCHER, "dispatcher_disable")
    token = (await login(api, "dispatcher_disable")).json()["access_token"]
    user.is_active = False
    await db_session.flush()
    assert (await api.get("/api/v1/auth/me", headers=bearer(token))).status_code == 401


# ---------------------------------------------------------------- startup secret check
@pytest.mark.parametrize("secret", ["dev-only-secret", "change_me_to_a_long_random_string", "short"])
def test_weak_secret_refused_outside_dev(secret: str) -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(env="production", jwt_secret=secret).check_secrets()


def test_access_token_default_lifetime_is_15_minutes() -> None:
    """D-023. A local .env can override it (JWT_EXPIRE_MINUTES); .env.example now says 15 (CR-002)."""
    assert Settings.model_fields["jwt_expire_minutes"].default == 15


def test_strong_secret_and_dev_mode_accepted() -> None:
    Settings(env="production", jwt_secret="x" * 40).check_secrets()
    Settings(env="dev", jwt_secret="dev-only-secret").check_secrets()
