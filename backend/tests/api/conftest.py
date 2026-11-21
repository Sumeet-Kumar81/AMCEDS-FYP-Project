"""API test fixtures (B1-A1-14/15): an HTTP client whose database session is the rolled-back test
session, and helpers to create SIMULATED users and sign them in."""
from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone

import bcrypt
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core import security
from app.core.security import create_token, hash_password, new_session_id
from app.main import app
from app.models import Assignment, Incident, User, UserSession, Vehicle
from app.schemas.auth import UserRole

PASSWORD = "SIMULATED-pass-123"


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    real = bcrypt.gensalt
    monkeypatch.setattr(security.bcrypt, "gensalt", lambda: real(rounds=4))  # tests only


@pytest.fixture
async def api(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async def override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


MakeUser = Callable[..., Awaitable[User]]


@pytest.fixture
def make_user(db_session: AsyncSession) -> MakeUser:
    counter = {"n": 0}

    async def make(role: UserRole | str, username: str | None = None, *, password: str = PASSWORD,
                   is_active: bool = True) -> User:
        counter["n"] += 1
        user = User(full_name=f"SIMULATED {role} {counter['n']}", username=username or f"{role}_{counter['n']}",
                    password_hash=hash_password(password), role=UserRole(role).value, is_active=is_active)
        db_session.add(user)
        await db_session.flush()
        return user

    return make


SignIn = Callable[[User], Awaitable[dict[str, str]]]


@pytest.fixture
def sign_in(db_session: AsyncSession) -> SignIn:
    """Open a session row for ``user`` and return the Authorization header (no password round trip)."""

    async def make(user: User) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        session = UserSession(session_id=new_session_id(), user_id=user.user_id, created_at=now, last_activity_at=now)
        db_session.add(session)
        await db_session.flush()
        token, _ = create_token(kind="access", user_id=user.user_id, session_id=session.session_id, role=UserRole(user.role))
        return {"Authorization": f"Bearer {token}"}

    return make


@pytest.fixture
def driver_assignment(db_session: AsyncSession, make_user: MakeUser) -> Callable[[User], Awaitable[int]]:
    """Create a vehicle driven by ``driver`` and an approved (open) assignment for it."""

    async def make(driver: User) -> int:
        dispatcher = await make_user(UserRole.DISPATCHER)
        vehicle = Vehicle(vehicle_type="ambulance", plate_number=f"SIM-TEST-{driver.user_id}", driver_id=driver.user_id)
        incident = Incident(channel="web", original_text="SIMULATED test incident")
        db_session.add_all([vehicle, incident])
        await db_session.flush()
        assignment = Assignment(incident_id=incident.incident_id, vehicle_id=vehicle.vehicle_id, approved_by=dispatcher.user_id)
        db_session.add(assignment)
        await db_session.flush()
        return assignment.assignment_id

    return make
