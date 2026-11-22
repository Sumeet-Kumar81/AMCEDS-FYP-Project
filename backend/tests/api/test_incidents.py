"""Incident queue and detail API (B1-A1-20): order, filters, roles, C-1 shapes, current recommendations
with plates, read-only. SIMULATED data on the rolled-back test database."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AuditLog, DuplicateCandidate, Incident, Recommendation, User, Vehicle
from app.schemas.auth import UserRole
from app.schemas.incident import IncidentDetailOut, IncidentSummaryOut

pytestmark = pytest.mark.db
T0 = datetime(2026, 11, 22, 8, 0, tzinfo=timezone.utc)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "contracts" / "incident_detail.json"


def pt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


@pytest.fixture
async def dispatcher(make_user, sign_in) -> dict[str, str]:
    return await sign_in(await make_user(UserRole.DISPATCHER))


@pytest.fixture
def add(db_session: AsyncSession):
    async def make(minutes: int = 0, **cols) -> Incident:
        row = Incident(channel=cols.pop("channel", "web"), original_text=cols.pop("original_text", "SIMULATED report"),
                       received_at=T0 + timedelta(minutes=minutes), **cols)
        db_session.add(row)
        await db_session.flush()
        return row

    return make


async def vehicle(db: AsyncSession, plate: str, vtype: str = "ambulance") -> Vehicle:
    v = Vehicle(vehicle_type=vtype, plate_number=plate, status="available")
    db.add(v)
    await db.flush()
    return v


# ---------------------------------------------------------------- queue order and filters
async def test_queue_is_critical_high_unknown_medium_low_then_longest_waiting(api, dispatcher, add) -> None:
    low = await add(0, severity="low", status="triaged")
    med = await add(1, severity="medium", status="triaged")
    unknown = await add(2, status="new")
    high_new = await add(5, severity="high", status="needs_check")
    high_old = await add(3, severity="high", status="triaged")
    crit = await add(9, severity="critical", status="triaged")
    r = await api.get("/api/v1/incidents", headers=dispatcher)
    assert r.status_code == 200
    ids = [i["incident_id"] for i in r.json()]
    assert ids == [crit.incident_id, high_old.incident_id, high_new.incident_id, unknown.incident_id,
                   med.incident_id, low.incident_id]


async def test_queue_hides_closed_and_fake_unless_asked(api, dispatcher, add) -> None:
    open_ = await add(0, status="triaged", severity="low")
    closed = await add(1, status="closed", severity="critical")
    fake = await add(2, status="fake", severity="high")
    default = [i["incident_id"] for i in (await api.get("/api/v1/incidents", headers=dispatcher)).json()]
    assert default == [open_.incident_id]
    everything = (await api.get("/api/v1/incidents", params={"include_closed": "true"}, headers=dispatcher)).json()
    assert {i["incident_id"] for i in everything} == {open_.incident_id, closed.incident_id, fake.incident_id}
    only_fake = (await api.get("/api/v1/incidents", params={"status": "fake"}, headers=dispatcher)).json()
    assert [i["incident_id"] for i in only_fake] == [fake.incident_id]


async def test_queue_filters_by_status_and_severity_including_unknown(api, dispatcher, add) -> None:
    a = await add(0, status="needs_check", severity="high")
    b = await add(1, status="new")
    await add(2, status="triaged", severity="low")
    r = await api.get("/api/v1/incidents", params=[("severity", "high"), ("severity", "unknown")], headers=dispatcher)
    assert [i["incident_id"] for i in r.json()] == [a.incident_id, b.incident_id]
    r = await api.get("/api/v1/incidents", params={"status": "needs_check"}, headers=dispatcher)
    assert [i["incident_id"] for i in r.json()] == [a.incident_id]


async def test_queue_pages(api, dispatcher, add) -> None:
    rows = [await add(m, status="triaged", severity="medium") for m in range(5)]
    page = (await api.get("/api/v1/incidents", params={"limit": 2, "offset": 2}, headers=dispatcher)).json()
    assert [i["incident_id"] for i in page] == [rows[2].incident_id, rows[3].incident_id]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"offset": -1}, {"severity": "extreme"},
                                    {"status": "dispatched_now"}])
async def test_bad_query_is_422(api, dispatcher, params) -> None:
    r = await api.get("/api/v1/incidents", params=params, headers=dispatcher)
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


async def test_queue_card_is_c1_with_every_location_shape(api, dispatcher, add) -> None:
    gps = await add(0, status="triaged", severity="high", location=pt(27.7052, 68.8574), location_source="gps",
                    location_text="near Clock Tower", confidence=0.88, trust_score=60, trust_tier="medium",
                    review_reasons=["vehicle_shortage"], language="Roman Urdu", incident_type="accident",
                    victims_estimate=3)
    words = await add(1, status="needs_check", severity="high", location_source="text", location_text="Minara Road")
    none = await add(2, status="new", review_reasons=["location_unknown"])
    cards = {i["incident_id"]: i for i in (await api.get("/api/v1/incidents", headers=dispatcher)).json()}
    for card in cards.values():
        IncidentSummaryOut.model_validate(card)
    assert cards[gps.incident_id]["location"] == {"lat": 27.7052, "lon": 68.8574, "text": "near Clock Tower", "source": "gps"}
    assert cards[gps.incident_id]["confidence"] == 0.88 and cards[gps.incident_id]["review_reasons"] == ["vehicle_shortage"]
    assert cards[words.incident_id]["location"] == {"lat": None, "lon": None, "text": "Minara Road", "source": "text"}
    assert cards[none.incident_id]["location"]["source"] == "unknown"
    assert cards[none.incident_id]["reference_no"].startswith("INC-")


async def test_a_record_that_breaks_its_own_location_rule_is_shown_honestly(api, dispatcher, add) -> None:
    broken = await add(0, status="new", location_source="gps")  # "gps" but no point saved
    r = await api.get(f"/api/v1/incidents/{broken.incident_id}", headers=dispatcher)
    assert r.status_code == 200 and r.json()["location"]["source"] == "unknown"


# ---------------------------------------------------------------- detail
async def test_detail_has_the_report_ai_trust_and_current_recommendations_with_plates(api, dispatcher, add, db_session) -> None:
    amb1, amb2 = await vehicle(db_session, "SIM-T-AMB-1"), await vehicle(db_session, "SIM-T-AMB-2")
    triage = {"incident_type": "accident", "type_confidence": 0.93, "severity": "high", "severity_confidence": 0.81,
              "victims_estimate": 3, "victims_confidence": 0.7, "language": "Roman Urdu", "language_confidence": 0.9,
              "overall_confidence": 0.88, "missing_fields": []}
    row = await add(0, status="triaged", severity="high", incident_type="accident", victims_estimate=3,
                    original_text="SIMULATED: Clock Tower ke paas bus accident, 3 log zakhmi", reporter_name="SIMULATED Ali",
                    location=pt(27.7052, 68.8574), location_source="gps", confidence=0.88, trust_score=60,
                    trust_tier="medium", ai_details={"triage": triage, "trust_action": "continue_and_confirm"},
                    trust_signals=[{"code": "real_details", "points": 10, "detail": "the message names a place"}],
                    allocation_summary={"needed": {"ambulance": 1}, "shortage": None, "routing_mode": "straight_line"})
    db_session.add_all([
        Recommendation(incident_id=row.incident_id, vehicle_id=amb2.vehicle_id, rank=2, eta_seconds=200, distance_meters=2000,
                       vehicle_type="ambulance", eta_is_approximate=True, is_spare=True, batch_no=2, is_current=True),
        Recommendation(incident_id=row.incident_id, vehicle_id=amb1.vehicle_id, rank=1, eta_seconds=80, distance_meters=900,
                       vehicle_type="ambulance", eta_is_approximate=True, batch_no=2, is_current=True),
        Recommendation(incident_id=row.incident_id, vehicle_id=amb2.vehicle_id, rank=1, eta_seconds=999, distance_meters=9999,
                       vehicle_type="ambulance", eta_is_approximate=True, batch_no=1, is_current=False),  # old round
    ])
    await db_session.flush()
    r = await api.get(f"/api/v1/incidents/{row.incident_id}", headers=dispatcher)
    assert r.status_code == 200
    body = IncidentDetailOut.model_validate(r.json())
    assert body.original_text == "SIMULATED: Clock Tower ke paas bus accident, 3 log zakhmi"
    assert body.ai_details["triage"]["type_confidence"] == 0.93
    assert [s.code for s in body.trust_signals] == ["real_details"] and body.trust_signals[0].points == 10
    assert [(x.rank, x.plate_number, x.is_spare) for x in body.recommendations] == [
        (1, "SIM-T-AMB-1", False), (2, "SIM-T-AMB-2", True)]  # current round only, rank order
    assert body.allocation_summary["routing_mode"] == "straight_line"
    assert body.assignments == [] and body.dispatcher_decision is None and body.duplicate_candidates == []


async def test_detail_carries_duplicates_and_the_dispatchers_decision(api, dispatcher, add, db_session, make_user) -> None:
    approver: User = await make_user(UserRole.DISPATCHER)
    amb = await vehicle(db_session, "SIM-T-AMB-3")
    a, b = await add(0, status="dispatched", severity="high"), await add(1, status="triaged", severity="high")
    db_session.add_all([
        DuplicateCandidate(incident_id=a.incident_id, candidate_incident_id=b.incident_id, match_confidence=72,
                           distance_m=150, time_diff_s=60, similarity=0.6, decision="possible"),
        Assignment(incident_id=a.incident_id, vehicle_id=amb.vehicle_id, approved_by=approver.user_id),
    ])
    await db_session.flush()
    body = (await api.get(f"/api/v1/incidents/{a.incident_id}", headers=dispatcher)).json()
    assert body["duplicate_candidates"][0]["match_confidence"] == 72 and body["duplicate_candidates"][0]["decision"] == "possible"
    assert body["assignments"][0]["vehicle_id"] == amb.vehicle_id
    assert body["dispatcher_decision"]["approved_by"] == approver.user_id


async def test_missing_incident_is_404(api, dispatcher) -> None:
    r = await api.get("/api/v1/incidents/987654", headers=dispatcher)
    assert r.status_code == 404 and r.json() == {"code": "not_found", "message": "No such incident.", "details": None}


async def test_plate_number_is_optional_so_v1_data_stays_valid() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert IncidentDetailOut.model_validate(data).recommendations[0].plate_number  # the v1.2 example has plates
    for rec in data["recommendations"]:
        rec.pop("plate_number")  # what a v1/v1.1 record looks like
    assert IncidentDetailOut.model_validate(data).recommendations[0].plate_number is None


# ---------------------------------------------------------------- roles and read-only
@pytest.mark.parametrize("role", [UserRole.DRIVER, UserRole.ADMIN])
async def test_only_dispatchers(api, make_user, sign_in, add, role) -> None:
    row = await add(0, status="triaged")
    headers = await sign_in(await make_user(role))
    for path in ("/api/v1/incidents", f"/api/v1/incidents/{row.incident_id}"):
        r = await api.get(path, headers=headers)
        assert r.status_code == 403 and r.json()["code"] == "forbidden"


async def test_not_signed_in_is_401(api, add) -> None:
    row = await add(0)
    assert (await api.get(f"/api/v1/incidents/{row.incident_id}")).status_code == 401


async def test_reading_changes_nothing(api, dispatcher, add, db_session) -> None:
    amb = await vehicle(db_session, "SIM-T-AMB-4")
    row = await add(0, status="triaged", severity="critical")
    db_session.add(Recommendation(incident_id=row.incident_id, vehicle_id=amb.vehicle_id, rank=1, eta_seconds=60,
                                  distance_meters=500, vehicle_type="ambulance", eta_is_approximate=True))
    await db_session.flush()
    audits = await db_session.scalar(select(func.count()).select_from(AuditLog))
    await api.get("/api/v1/incidents", headers=dispatcher)
    await api.get(f"/api/v1/incidents/{row.incident_id}", headers=dispatcher)
    await db_session.refresh(row)
    await db_session.refresh(amb)
    assert row.status == "triaged" and amb.status == "available"  # never locked by being shown (rule 6)
    assert await db_session.scalar(select(func.count()).select_from(Assignment)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == audits
