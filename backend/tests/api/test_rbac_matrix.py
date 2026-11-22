"""Role matrix (B1-A1-15): every route × {not signed in, dispatcher, driver, admin}.

Private routes answer 401 when not signed in, 403 for a wrong role and, for the right role, the
contracted 501 (or the real answer once built). The test fails if a route is not in ROLES, so a new
endpoint cannot be added without deciding who may call it.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
import pytest

from app.main import app
from app.schemas.auth import UserRole
from tests.api.test_api_contract import CONTRACT, PATH_VALUES

pytestmark = pytest.mark.db

D, R, A = UserRole.DISPATCHER, UserRole.DRIVER, UserRole.ADMIN
PUBLIC, SIMULATOR = "public", "simulator"

ROLES: dict[tuple[str, str], str | frozenset[UserRole]] = {
    ("GET", "/health"): PUBLIC,
    ("POST", "/api/v1/reports"): PUBLIC,
    ("POST", "/api/v1/reports/voice"): PUBLIC,
    ("POST", "/api/v1/reports/{reference_no}/confirmation"): PUBLIC,
    ("POST", "/api/v1/intake/sms"): SIMULATOR,
    ("POST", "/api/v1/intake/voice"): SIMULATOR,
    ("POST", "/api/v1/auth/login"): PUBLIC,
    ("POST", "/api/v1/auth/refresh"): PUBLIC,
    ("POST", "/api/v1/auth/logout"): frozenset({D, R, A}),
    ("GET", "/api/v1/auth/me"): frozenset({D, R, A}),
    **{(m, p): frozenset({D}) for m, p in [
        ("GET", "/api/v1/incidents"), ("GET", "/api/v1/incidents/{incident_id}"),
        ("PATCH", "/api/v1/incidents/{incident_id}"), ("GET", "/api/v1/incidents/{incident_id}/audio"),
        ("POST", "/api/v1/duplicate-candidates/{candidate_id}/confirm"),
        ("POST", "/api/v1/duplicate-candidates/{candidate_id}/reject"), ("GET", "/api/v1/review-queue"),
        ("POST", "/api/v1/incidents/{incident_id}/confirmation-requests"),
        ("POST", "/api/v1/incidents/{incident_id}/review-decision"), ("POST", "/api/v1/incidents/{incident_id}/dispatch"),
        ("PATCH", "/api/v1/assignments/{assignment_id}/hospital"), ("POST", "/api/v1/assignments/{assignment_id}/cancel"),
        ("GET", "/api/v1/vehicles"), ("GET", "/api/v1/fleet/live"),
    ]},
    ("GET", "/api/v1/hospitals"): frozenset({D, R}),
    ("GET", "/api/v1/routing/route"): frozenset({D, R}),
    **{(m, p): frozenset({R}) for m, p in [
        ("POST", "/api/v1/driver/duty/start"), ("POST", "/api/v1/driver/duty/end"),
        ("GET", "/api/v1/driver/assignments/current"), ("POST", "/api/v1/driver/assignments/{assignment_id}/accept"),
        ("POST", "/api/v1/driver/assignments/{assignment_id}/decline"),
        ("POST", "/api/v1/driver/assignments/{assignment_id}/status"), ("POST", "/api/v1/driver/locations"),
    ]},
    **{(m, p): frozenset({A}) for (m, p) in CONTRACT if p.startswith("/api/v1/admin/")},
    **{(m, p): frozenset({D, A}) for (m, p) in CONTRACT if p.startswith("/api/v1/analytics/")},
}
PRIVATE = sorted(k for k, v in ROLES.items() if isinstance(v, frozenset))
DRIVER_OWNED = {p for (_, p) in ROLES if p.startswith("/api/v1/driver/assignments/{assignment_id}")}
REAL = {("POST", "/api/v1/auth/logout"): 204, ("GET", "/api/v1/auth/me"): 200,
        ("GET", "/api/v1/incidents"): 200, ("GET", "/api/v1/incidents/{incident_id}"): 404,  # 404: no incident 1 in the test data
        ("GET", "/api/v1/vehicles"): 200, ("POST", "/api/v1/incidents/{incident_id}/dispatch"): 422,  # 422: the matrix sends no body
        # B1-A1-26: hospitals for D and R; the matrix driver has no open assignment of their own (204), is not on
        # duty (accept 409) and sends no body (decline/status/hospital 422); dispatcher actions on assignment 1 → 404.
        ("GET", "/api/v1/hospitals"): 200, ("GET", "/api/v1/driver/assignments/current"): 204,
        ("POST", "/api/v1/driver/assignments/{assignment_id}/accept"): 409,
        ("POST", "/api/v1/driver/assignments/{assignment_id}/decline"): 422,
        ("POST", "/api/v1/driver/assignments/{assignment_id}/status"): 422,
        ("PATCH", "/api/v1/assignments/{assignment_id}/hospital"): 422, ("POST", "/api/v1/assignments/{assignment_id}/cancel"): 404}
DOC = Path(os.environ.get("API_CONTRACT_DOC", Path(__file__).resolve().parents[3] / "docs" / "API_CONTRACT.md"))


def concrete(path: str, assignment_id: int | None = None) -> str:
    values = {**PATH_VALUES, **({"assignment_id": str(assignment_id)} if assignment_id else {})}
    return re.sub(r"\{(\w+)\}", lambda m: values[m.group(1)], path)


def test_every_route_has_a_role_rule() -> None:
    operations = {(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops}
    assert set(ROLES) == operations, "a route without a role rule (or a rule for a missing route)"


def test_contract_document_roles_match() -> None:
    if not DOC.exists():
        pytest.skip(f"docs/API_CONTRACT.md not visible here ({DOC}); runs in CI and with the repo mounted")
    letters = {"D": D, "R": R, "A": A}
    documented: dict[tuple[str, str], object] = {}
    for method, path, role in re.findall(r"^\| `(\w+)` \| `(/[^`]*)` \| ([^|]+) \|", DOC.read_text(encoding="utf-8"), re.M):
        role = role.strip()
        if role.startswith("P"):
            documented[(method, path)] = PUBLIC
        elif role == "S":
            documented[(method, path)] = SIMULATOR
        elif role == "staff":
            documented[(method, path)] = frozenset({D, R, A})
        else:
            documented[(method, path)] = frozenset(letters[x.strip()[0]] for x in re.sub(r"\(.*\)", "", role).split(","))
    assert documented == ROLES


@pytest.mark.parametrize(("method", "path"), PRIVATE, ids=str)
async def test_not_signed_in_is_401(api: httpx.AsyncClient, method: str, path: str) -> None:
    r = await api.request(method, concrete(path))
    assert r.status_code == 401 and r.json()["code"] == "unauthorized"
    assert r.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("role", [D, R, A], ids=str)
@pytest.mark.parametrize(("method", "path"), PRIVATE, ids=str)
async def test_role_matrix(api, make_user, sign_in, driver_assignment, method: str, path: str, role: UserRole) -> None:
    user = await make_user(role)
    headers = await sign_in(user)
    assignment_id = await driver_assignment(user) if (role is R and path in DRIVER_OWNED) else None
    r = await api.request(method, concrete(path, assignment_id), headers=headers)
    allowed = ROLES[(method, path)]
    if role not in allowed:
        assert r.status_code == 403 and r.json()["code"] == "forbidden", r.text
    elif (method, path) in REAL:
        assert r.status_code == REAL[(method, path)], r.text
    else:
        assert r.status_code == 501, r.text
        assert r.json() == {"code": "not_implemented", "details": {"task": CONTRACT[(method, path)]},
                            "message": f"This endpoint is in the API contract but is not implemented yet "
                                       f"(task {CONTRACT[(method, path)]})."}


@pytest.mark.parametrize("path", sorted(DRIVER_OWNED))
async def test_driver_cannot_act_on_another_drivers_assignment(api, make_user, sign_in, driver_assignment, path: str) -> None:
    """TC-48."""
    owner, other = await make_user(R), await make_user(R)
    assignment_id = await driver_assignment(owner)
    r = await api.post(concrete(path, assignment_id), headers=await sign_in(other))
    assert r.status_code == 403 and r.json()["code"] == "forbidden"


async def test_missing_assignment_is_404_for_a_driver(api, make_user, sign_in) -> None:
    driver = await make_user(R)
    r = await api.post("/api/v1/driver/assignments/999999/accept", headers=await sign_in(driver))
    assert r.status_code == 404


async def test_role_is_read_from_the_database_not_the_token(api, make_user, sign_in, db_session) -> None:
    user = await make_user(D)
    headers = await sign_in(user)  # token says dispatcher
    user.role = "admin"
    await db_session.flush()
    assert (await api.get("/api/v1/incidents", headers=headers)).status_code == 403
    assert (await api.get("/api/v1/admin/users", headers=headers)).status_code == 501


@pytest.mark.parametrize(("method", "path"), sorted(k for k, v in ROLES.items() if v == SIMULATOR), ids=str)
async def test_simulator_routes_stay_501_until_d014(api: httpx.AsyncClient, method: str, path: str) -> None:
    assert (await api.request(method, path)).status_code == 501
