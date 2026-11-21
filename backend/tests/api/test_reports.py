"""POST /api/v1/reports (B1-A1-16): save before processing. TC-01, TC-03, TC-04, TC-50, database down."""
from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.deps import get_db
from app.main import app
from app.models import AuditLog, Caller, Incident
from app.schemas.incident import REFERENCE_NO_PATTERN
from app.services.settings import REGISTRY

pytestmark = pytest.mark.db
URL = "/api/v1/reports"


async def post(api: httpx.AsyncClient, **body) -> httpx.Response:
    return await api.post(URL, json={"description": "SIMULATED bus accident near the market", **body})


async def saved(db: AsyncSession, reference_no: str) -> Incident:
    return await db.scalar(select(Incident).where(Incident.reference_no == reference_no))


# ---------------------------------------------------------------- TC-01 save and reference
async def test_tc01_report_is_saved_and_gets_a_real_reference(api, db_session) -> None:
    r = await post(api, channel="web")
    assert r.status_code == 201, r.text
    body = r.json()
    assert re.fullmatch(REFERENCE_NO_PATTERN, body["reference_no"]) and body["status"] == "new" and body["received_at"]
    incident = await saved(db_session, body["reference_no"])
    assert incident is not None and incident.original_text == "SIMULATED bus accident near the market"
    assert (incident.status, incident.pipeline_state, incident.channel) == ("new", "pending", "web")
    assert set(incident.settings_snapshot) == set(REGISTRY)
    audit = await db_session.scalar(select(AuditLog).where(AuditLog.incident_id == incident.incident_id))
    assert audit.action == "report.received"


async def test_app_channel_and_gps_location(api, db_session) -> None:
    r = await post(api, channel="app", lat=27.7052, lon=68.8574)
    incident = await saved(db_session, r.json()["reference_no"])
    assert incident.location_source == "gps" and incident.location is not None and incident.caller_gps is not None
    assert incident.review_reasons == []


async def test_address_words_only(api, db_session) -> None:
    r = await post(api, address_text="  near the Sukkur barrage  ")
    incident = await saved(db_session, r.json()["reference_no"])
    assert (incident.location_source, incident.location_text, incident.location) == ("text", "near the Sukkur barrage", None)


async def test_tc03_unknown_location_is_saved_with_a_reason(api, db_session) -> None:
    r = await post(api)
    assert r.status_code == 201
    incident = await saved(db_session, r.json()["reference_no"])
    assert incident.location_source == "unknown" and incident.review_reasons == ["location_unknown"]


# ---------------------------------------------------------------- TC-04 resend
async def test_tc04_resend_with_the_same_client_request_id_saves_once(api, db_session) -> None:
    first = await post(api, client_request_id="SIMULATED-app-1234")
    again = await post(api, client_request_id="SIMULATED-app-1234")
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["reference_no"] == again.json()["reference_no"]
    count = await db_session.scalar(select(func.count()).select_from(Incident)
                                    .where(Incident.client_request_id == "SIMULATED-app-1234"))
    assert count == 1


# ---------------------------------------------------------------- TC-50 and languages
async def test_tc50_sql_text_is_stored_verbatim_and_the_table_survives(api, db_session) -> None:
    evil = "'; DROP TABLE incidents;-- SIMULATED"
    r = await post(api, description=evil, address_text="x'); DELETE FROM callers;--")
    assert r.status_code == 201
    assert (await saved(db_session, r.json()["reference_no"])).original_text == evil
    assert await db_session.scalar(select(func.count()).select_from(Incident)) >= 1


@pytest.mark.parametrize("text", ["مارکیٹ کے قریب بس کا حادثہ، کئی لوگ زخمی", "Bazar wate bus jo haadso, ghana maanhu zakhmi",
                                  "accident near Sukkur bridge, 3 log zakhmi"])
async def test_urdu_sindhi_and_mixed_text_stored_as_written(api, db_session, text: str) -> None:
    r = await post(api, description=text)
    assert (await saved(db_session, r.json()["reference_no"])).original_text == text


# ---------------------------------------------------------------- callers
async def test_same_phone_is_the_same_caller(api, db_session) -> None:
    a = await post(api, reporter_phone="+92 300-111 2222")
    b = await post(api, reporter_phone="+923001112222")
    ia, ib = await saved(db_session, a.json()["reference_no"]), await saved(db_session, b.json()["reference_no"])
    assert ia.caller_id is not None and ia.caller_id == ib.caller_id
    assert (await db_session.get(Caller, ia.caller_id)).phone_number == "+923001112222"


async def test_device_then_phone_fills_in_the_same_caller(api, db_session) -> None:
    a = await post(api, device_id="SIMULATED-device-9")
    b = await post(api, device_id="SIMULATED-device-9", reporter_phone="03001234567")
    ia, ib = await saved(db_session, a.json()["reference_no"]), await saved(db_session, b.json()["reference_no"])
    assert ia.caller_id == ib.caller_id
    assert (await db_session.get(Caller, ia.caller_id)).phone_number == "03001234567"


async def test_anonymous_report_has_no_caller(api, db_session) -> None:
    r = await post(api)
    assert (await saved(db_session, r.json()["reference_no"])).caller_id is None


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize("body", [
    {"description": ""}, {"description": "   "}, {"description": "x" * 2001},
    {"channel": "sms"}, {"channel": "voice"}, {"channel": "mobile"},
    {"lat": 27.7}, {"lon": 68.8}, {"lat": 91, "lon": 0},
    {"reporter_phone": "call me"}, {"reporter_phone": "12"}, {"reporter_name": "n" * 101},
    {"client_request_id": "c" * 101}, {"made_up_field": 1},
])
async def test_invalid_reports_are_422_and_nothing_is_saved(api, db_session, body: dict) -> None:
    before = await db_session.scalar(select(func.count()).select_from(Incident))
    r = await api.post(URL, json={"description": "SIMULATED report", **body})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert "reference_no" not in r.text
    assert await db_session.scalar(select(func.count()).select_from(Incident)) == before


# ---------------------------------------------------------------- database down → 503, never a reference
async def test_database_down_gives_503_and_no_reference_number() -> None:
    dead = create_async_engine("postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none")

    async def broken() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(dead) as session:
            yield session

    app.dependency_overrides[get_db] = broken
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(URL, json={"description": "SIMULATED report"})
    finally:
        app.dependency_overrides.pop(get_db, None)
        await dead.dispose()
    assert r.status_code == 503 and r.json()["code"] == "service_unavailable"
    assert "INC-" not in r.text and "1122" in r.json()["message"]


async def test_failing_commit_gives_503_and_no_reference(api, db_session, monkeypatch) -> None:
    from sqlalchemy.exc import OperationalError

    async def fail() -> None:
        raise OperationalError("COMMIT", {}, Exception("connection lost"))

    monkeypatch.setattr(db_session, "commit", fail)
    r = await post(api)
    assert r.status_code == 503 and "INC-" not in r.text


# ---------------------------------------------------------------- no AI in the request path (D-011)
def test_no_ai_code_is_loaded_by_the_api() -> None:
    backend = Path(__file__).resolve().parents[2]
    code = ("import sys, app.main\n"
            "loaded = sorted(m for m in sys.modules if m.startswith(('app.agents', 'app.llm', 'app.workers')))\n"
            "print(','.join(loaded))")
    out = subprocess.run([sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == ""
