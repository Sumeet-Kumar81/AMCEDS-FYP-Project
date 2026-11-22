"""Contract C-4 tests (B1-A1-04): every contracted endpoint exists, unbuilt ones answer 501, errors use one body."""
import os
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.main import app

# SDS v1.1 Table 4.3 (+ IMPLEMENTATION_PLAN §4.3 for the admin methods). Same list as docs/API_CONTRACT.md §3.
CONTRACT: dict[tuple[str, str], str] = {
    ("GET", "/health"): "exists",
    ("POST", "/api/v1/reports"): "exists",  # built in B1-A1-16
    ("POST", "/api/v1/reports/voice"): "B1-A1-17",
    ("POST", "/api/v1/reports/{reference_no}/confirmation"): "B1-A1-24",
    ("POST", "/api/v1/intake/sms"): "B4-01",
    ("POST", "/api/v1/intake/voice"): "B4-02",
    ("POST", "/api/v1/auth/login"): "exists",  # built in B1-A1-14
    ("POST", "/api/v1/auth/refresh"): "exists",
    ("POST", "/api/v1/auth/logout"): "exists",
    ("GET", "/api/v1/auth/me"): "exists",
    ("GET", "/api/v1/incidents"): "exists",  # built in B1-A1-20
    ("GET", "/api/v1/incidents/{incident_id}"): "exists",  # built in B1-A1-20
    ("PATCH", "/api/v1/incidents/{incident_id}"): "B1-A1-21",
    ("GET", "/api/v1/incidents/{incident_id}/audio"): "B1-A1-17",
    ("POST", "/api/v1/duplicate-candidates/{candidate_id}/confirm"): "B1-A1-22",
    ("POST", "/api/v1/duplicate-candidates/{candidate_id}/reject"): "B1-A1-22",
    ("GET", "/api/v1/review-queue"): "B1-A1-23",
    ("POST", "/api/v1/incidents/{incident_id}/confirmation-requests"): "B1-A1-24",
    ("POST", "/api/v1/incidents/{incident_id}/review-decision"): "B1-A1-23",
    ("POST", "/api/v1/incidents/{incident_id}/dispatch"): "B1-A1-25",
    ("PATCH", "/api/v1/assignments/{assignment_id}/hospital"): "B1-A1-26",
    ("POST", "/api/v1/assignments/{assignment_id}/cancel"): "B1-A1-26",
    ("GET", "/api/v1/vehicles"): "B1-A1-25",
    ("GET", "/api/v1/fleet/live"): "B1-A1-27",
    ("GET", "/api/v1/hospitals"): "B1-A1-26",
    ("GET", "/api/v1/routing/route"): "B1-A2-15",
    ("POST", "/api/v1/driver/duty/start"): "B1-A1-27",
    ("POST", "/api/v1/driver/duty/end"): "B1-A1-27",
    ("GET", "/api/v1/driver/assignments/current"): "B1-A1-26",
    ("POST", "/api/v1/driver/assignments/{assignment_id}/accept"): "B1-A1-26",
    ("POST", "/api/v1/driver/assignments/{assignment_id}/decline"): "B1-A1-26",
    ("POST", "/api/v1/driver/assignments/{assignment_id}/status"): "B1-A1-26",
    ("POST", "/api/v1/driver/locations"): "B1-A1-27",
    ("GET", "/api/v1/admin/users"): "B1-A1-31",
    ("POST", "/api/v1/admin/users"): "B1-A1-31",
    ("PATCH", "/api/v1/admin/users/{user_id}"): "B1-A1-31",
    ("GET", "/api/v1/admin/vehicles"): "B1-A1-31",
    ("POST", "/api/v1/admin/vehicles"): "B1-A1-31",
    ("PATCH", "/api/v1/admin/vehicles/{vehicle_id}"): "B1-A1-31",
    ("DELETE", "/api/v1/admin/vehicles/{vehicle_id}"): "B1-A1-31",
    ("GET", "/api/v1/admin/hospitals"): "B1-A1-31",
    ("POST", "/api/v1/admin/hospitals"): "B1-A1-31",
    ("PATCH", "/api/v1/admin/hospitals/{hospital_id}"): "B1-A1-31",
    ("GET", "/api/v1/admin/settings"): "B1-A1-31",
    ("PUT", "/api/v1/admin/settings/{key}"): "B1-A1-31",
    ("GET", "/api/v1/admin/audit-logs"): "B1-A1-31",
    ("GET", "/api/v1/analytics/incidents"): "B1-A1-32",
    ("GET", "/api/v1/analytics/performance"): "B1-A1-32",
    ("GET", "/api/v1/analytics/export"): "B1-A1-32",
}
STUBS = {k: v for k, v in CONTRACT.items() if v != "exists"}
# Stubs anyone may call. Every other stub needs a signed-in user with the right role and is checked
# (401 / 403 / 501) in test_rbac_matrix.py (B1-A1-15).
OPEN_STUBS = {k: v for k, v in STUBS.items() if k[1].startswith(("/api/v1/reports", "/api/v1/intake/"))}
PATH_VALUES = {"incident_id": "1", "candidate_id": "1", "assignment_id": "1", "user_id": "1",
               "vehicle_id": "1", "hospital_id": "1", "reference_no": "INC-000001", "key": "dup_auto_link"}
VALID_BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/v1/reports/voice"): {"files": {"audio": ("clip.wav", b"RIFF0000WAVE", "audio/wav")}},
}
DOC = Path(os.environ.get("API_CONTRACT_DOC", Path(__file__).resolve().parents[3] / "docs" / "API_CONTRACT.md"))


def openapi_operations() -> set[tuple[str, str]]:
    return {(m.upper(), p) for p, ops in app.openapi()["paths"].items() for m in ops}


def concrete(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: PATH_VALUES[m.group(1)], path)


# ---------------------------------------------------------------- the surface
def test_openapi_lists_exactly_the_contracted_endpoints() -> None:
    ops = openapi_operations()
    assert ops - set(CONTRACT) == set(), "endpoints in the code but not in the contract"
    assert set(CONTRACT) - ops == set(), "contracted endpoints missing from the code"
    assert len(CONTRACT) == 49  # /health + 48 from SDS v1.1 Table 4.3


def test_everything_except_health_is_under_api_v1() -> None:
    assert all(p.startswith("/api/v1/") for (_, p) in CONTRACT if p != "/health")


def test_contract_document_matches_openapi() -> None:
    if not DOC.exists():
        pytest.skip(f"docs/API_CONTRACT.md not visible here ({DOC}); runs in CI and with the repo mounted")
    rows = set(re.findall(r"^\| `(GET|POST|PATCH|PUT|DELETE)` \| `(/[^`]*)` \|", DOC.read_text(encoding="utf-8"), re.M))
    assert rows == openapi_operations()


# ---------------------------------------------------------------- stubs answer 501, never fake data
@pytest.mark.parametrize(("method", "path"), sorted(OPEN_STUBS), ids=lambda x: str(x))
async def test_open_stub_returns_501_with_contract_error_body(client: httpx.AsyncClient, method: str, path: str) -> None:
    r = await client.request(method, concrete(path), **VALID_BODIES.get((method, path), {}))
    assert r.status_code == 501, r.text
    assert r.json() == {
        "code": "not_implemented",
        "message": f"This endpoint is in the API contract but is not implemented yet (task {STUBS[(method, path)]}).",
        "details": {"task": STUBS[(method, path)]},
    }


# ---------------------------------------------------------------- error body
async def test_validation_error_uses_contract_body_and_hides_input(client: httpx.AsyncClient) -> None:
    secret = "SIMULATED-secret-password"
    r = await client.post("/api/v1/auth/login", json={"username": "", "password": secret})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error" and isinstance(body["details"], list)
    assert {"loc", "msg", "type"} <= set(body["details"][0])
    assert secret not in r.text


async def test_report_without_description_is_422_in_contract_shape(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/reports", json={"channel": "web", "description": "   "})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


async def test_bad_reference_number_is_422(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/reports/123/confirmation")
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


async def test_unknown_path_is_404_in_contract_shape(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/does-not-exist")
    assert r.status_code == 404 and r.json() == {"code": "not_found", "message": "Not Found", "details": None}


async def test_old_unprefixed_reports_path_is_gone(client: httpx.AsyncClient) -> None:
    r = await client.post("/reports", json={"description": "x"})
    assert r.status_code == 404


async def test_wrong_method_is_405_in_contract_shape(client: httpx.AsyncClient) -> None:
    r = await client.delete("/api/v1/incidents")
    assert r.status_code == 405 and r.json()["code"] == "method_not_allowed"


def test_openapi_documents_the_error_body_on_stubs() -> None:
    op = app.openapi()["paths"]["/api/v1/incidents"]["get"]
    assert op["responses"]["501"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorBody")


def test_openapi_shows_contract_shapes_where_defined() -> None:
    paths = app.openapi()["paths"]
    detail = paths["/api/v1/incidents/{incident_id}"]["get"]["responses"]["200"]["content"]["application/json"]
    assert detail["schema"]["$ref"].endswith("/IncidentDetailOut")
    login = paths["/api/v1/auth/login"]["post"]
    assert login["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/LoginIn")
