"""Assignment lifecycle (B1-A1-26): the whole trip with timestamps (TC-29 API part), decline frees the
vehicle and hands the incident back (TC-27), invalid order → 409 with nothing changed, another driver's
assignment → 403 (TC-48), cancel, hospital change, closing the incident, hospitals list. SIMULATED data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AuditLog, Hospital, Incident, Recommendation, User, Vehicle
from app.schemas.assignment import DriverAssignmentOut
from app.schemas.auth import UserRole

pytestmark = pytest.mark.db


def pt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class Trip:
    """One dispatched vehicle with its on-duty driver, ready for the driver's actions."""

    def __init__(self, db: AsyncSession, make_user, sign_in) -> None:
        self.db, self.make_user, self.sign_in = db, make_user, sign_in
        self.n = 0

    async def driver(self, on_duty: bool = True) -> tuple[User, dict[str, str]]:
        d: User = await self.make_user(UserRole.DRIVER)
        d.on_duty = on_duty
        return d, await self.sign_in(d)

    async def incident(self, status: str = "dispatched") -> Incident:
        row = Incident(channel="web", original_text="SIMULATED: bus accident near Clock Tower", status=status, severity="high",
                       incident_type="accident", victims_estimate=3, location=pt(27.7052, 68.8574), location_source="gps",
                       location_text="near Clock Tower")
        self.db.add(row)
        await self.db.flush()
        return row

    async def assign(self, incident: Incident, driver: User, *, status: str = "approved", hospital_id: int | None = None,
                     vehicle_status: str | None = None) -> tuple[Assignment, Vehicle]:
        self.n += 1
        dispatcher: User = await self.make_user(UserRole.DISPATCHER)
        v = Vehicle(vehicle_type="ambulance", plate_number=f"SIM-L-{self.n:03d}", driver_id=driver.user_id,
                    status=vehicle_status or ("assigned" if status == "approved" else "en_route"),
                    last_location=pt(27.70, 68.85), last_seen_at=datetime.now(timezone.utc))
        self.db.add(v)
        await self.db.flush()
        a = Assignment(incident_id=incident.incident_id, vehicle_id=v.vehicle_id, approved_by=dispatcher.user_id,
                       status=status, hospital_id=hospital_id)
        self.db.add(a)
        await self.db.flush()
        return a, v

    async def ready(self) -> None:
        await self.db.commit()  # a refused request rolls the session back; keep the set-up


@pytest.fixture
def trip(db_session, make_user, sign_in) -> Trip:
    return Trip(db_session, make_user, sign_in)


@pytest.fixture
async def dispatcher(make_user, sign_in) -> dict[str, str]:
    return await sign_in(await make_user(UserRole.DISPATCHER))


def a_url(a_id: int, action: str) -> str:
    return f"/api/v1/driver/assignments/{a_id}/{action}"


async def actions(db: AsyncSession, incident_id: int) -> list[str]:
    return list((await db.scalars(select(AuditLog.action).where(AuditLog.incident_id == incident_id).order_by(AuditLog.log_id))).all())


# ---------------------------------------------------------------- TC-29: the whole trip
async def test_tc29_whole_trip_with_timestamps_frees_the_vehicle_and_closes_the_incident(api, trip, db_session) -> None:
    driver, headers = await trip.driver()
    inc = await trip.incident()
    a, v = await trip.assign(inc, driver)
    await trip.ready()
    a_id, v_id, inc_id = a.assignment_id, v.vehicle_id, inc.incident_id

    r = await api.post(a_url(a_id, "accept"), headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["accepted_at"]
    steps = [("on_scene", "on_scene", "on_scene_at", "on_scene"), ("picked_up", "transporting", "picked_up_at", "on_scene"),
             ("at_hospital", "at_hospital", "at_hospital_at", "on_scene"), ("available", "available", "completed_at", "closed")]
    for step, vehicle_status, stamp, incident_status in steps:
        r = await api.post(a_url(a_id, "status"), json={"status": step}, headers=headers)
        assert r.status_code == 200, (step, r.text)
        assert r.json()[stamp] is not None
        v = await db_session.get(Vehicle, v_id)
        inc = await db_session.get(Incident, inc_id)
        await db_session.refresh(v)
        await db_session.refresh(inc)
        assert (v.status, inc.status) == (vehicle_status, incident_status), step
    body = r.json()
    assert body["status"] == "completed"
    times = [datetime.fromisoformat(body[k]) for k in ("approved_at", "accepted_at", "on_scene_at", "picked_up_at",
                                                       "at_hospital_at", "completed_at")]
    assert times == sorted(times)  # each step after the one before
    assert await actions(db_session, inc_id) == ["assignment.accepted"] + ["assignment.status_changed"] * 3 + [
        "vehicle.unlocked", "assignment.status_changed"]


async def test_a_trip_without_a_patient_ends_on_scene(api, trip, db_session) -> None:
    driver, headers = await trip.driver()
    inc = await trip.incident()
    a, v = await trip.assign(inc, driver, status="accepted")
    await trip.ready()
    for step in ("on_scene", "available"):
        assert (await api.post(a_url(a.assignment_id, "status"), json={"status": step}, headers=headers)).status_code == 200
    await db_session.refresh(v)
    assert v.status == "available"


async def test_the_incident_stays_open_while_another_vehicle_is_on_the_way(api, trip, db_session) -> None:
    d1, h1 = await trip.driver()
    d2, _ = await trip.driver()
    inc = await trip.incident(status="on_scene")
    a1, _ = await trip.assign(inc, d1, status="accepted", vehicle_status="on_scene")
    await trip.assign(inc, d2)
    await trip.ready()
    assert (await api.post(a_url(a1.assignment_id, "status"), json={"status": "available"}, headers=h1)).status_code == 200
    await db_session.refresh(inc)
    assert inc.status == "on_scene"  # the second vehicle is still on its way


async def test_a_freed_vehicle_can_be_dispatched_again(api, trip, dispatcher, db_session) -> None:
    driver, headers = await trip.driver()
    inc = await trip.incident()
    a, v = await trip.assign(inc, driver, status="accepted", vehicle_status="on_scene")
    await trip.ready()
    v_id = v.vehicle_id
    await api.post(a_url(a.assignment_id, "status"), json={"status": "available"}, headers=headers)
    other = await trip.incident(status="triaged")
    await trip.ready()
    r = await api.post(f"/api/v1/incidents/{other.incident_id}/dispatch", json={"vehicle_ids": [v_id]}, headers=dispatcher)
    assert r.status_code == 201


# ---------------------------------------------------------------- TC-27: decline
async def test_tc27_decline_frees_the_vehicle_and_hands_the_incident_back(api, trip, db_session) -> None:
    driver, headers = await trip.driver()
    inc = await trip.incident()
    a, v = await trip.assign(inc, driver)
    await trip.ready()
    r = await api.post(a_url(a.assignment_id, "decline"), json={"reason": "vehicle_problem"}, headers=headers)
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["decline_reason"]) == ("declined", "vehicle_problem") and r.json()["declined_at"]
    await db_session.refresh(v)
    await db_session.refresh(inc)
    assert v.status == "available"
    assert inc.status == "needs_check" and "vehicle_declined" in inc.review_reasons  # the dispatcher sends another
    [audit] = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "assignment.declined"))).all()
    assert audit.details["reason"] == "vehicle_problem"
    assert audit.details["incident_status"] == {"from": "dispatched", "to": "needs_check"}


async def test_a_decline_with_another_vehicle_still_going_keeps_the_incident_dispatched(api, trip, db_session) -> None:
    d1, h1 = await trip.driver()
    d2, _ = await trip.driver()
    inc = await trip.incident()
    a1, _ = await trip.assign(inc, d1)
    await trip.assign(inc, d2, status="accepted")
    await trip.ready()
    assert (await api.post(a_url(a1.assignment_id, "decline"), json={"reason": "too_far"}, headers=h1)).status_code == 200
    await db_session.refresh(inc)
    assert inc.status == "dispatched" and "vehicle_declined" not in inc.review_reasons


@pytest.mark.parametrize("body", [{}, {"reason": "tired_of_it"}, {"reason": "other", "note": "x"}])
async def test_decline_needs_a_reason_from_the_list(api, trip, body) -> None:
    driver, headers = await trip.driver()
    a, _ = await trip.assign(await trip.incident(), driver)
    await trip.ready()
    assert (await api.post(a_url(a.assignment_id, "decline"), json=body, headers=headers)).status_code == 422


# ---------------------------------------------------------------- order is enforced (C-7)
@pytest.mark.parametrize(("status", "action", "body"), [
    ("approved", "status", {"status": "picked_up"}),   # picked up before accepted
    ("approved", "status", {"status": "on_scene"}),    # no step before accepting
    ("accepted", "decline", {"reason": "other"}),      # cannot decline after accepting
    ("accepted", "accept", None),                      # twice
    ("completed", "accept", None),
    ("declined", "status", {"status": "available"}),
])
async def test_out_of_order_is_409_and_changes_nothing(api, trip, db_session, status, action, body) -> None:
    driver, headers = await trip.driver()
    inc = await trip.incident()
    a, v = await trip.assign(inc, driver, status=status, vehicle_status="en_route" if status == "accepted" else "assigned")
    await trip.ready()
    a_id, v_id, before = a.assignment_id, v.vehicle_id, v.status
    r = await api.post(a_url(a_id, action), json=body, headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"
    assert (await db_session.get(Assignment, a_id)).status == status
    assert (await db_session.get(Vehicle, v_id)).status == before


async def test_skipping_a_trip_step_is_409(api, trip, db_session) -> None:
    driver, headers = await trip.driver()
    a, _ = await trip.assign(await trip.incident(), driver, status="accepted")  # vehicle en_route
    await trip.ready()
    r = await api.post(a_url(a.assignment_id, "status"), json={"status": "at_hospital"}, headers=headers)
    assert r.status_code == 409 and r.json()["details"] == {"vehicle_status": "en_route", "step": "at_hospital"}


async def test_an_off_duty_driver_cannot_accept(api, trip, db_session) -> None:
    driver, headers = await trip.driver(on_duty=False)
    a, _ = await trip.assign(await trip.incident(), driver)
    await trip.ready()
    r = await api.post(a_url(a.assignment_id, "accept"), headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "driver_off_duty"


# ---------------------------------------------------------------- TC-48: only your own vehicle
@pytest.mark.parametrize(("action", "body"), [("accept", None), ("decline", {"reason": "other"}), ("status", {"status": "on_scene"})])
async def test_tc48_another_drivers_assignment_is_403(api, trip, db_session, action, body) -> None:
    owner, _ = await trip.driver()
    _, intruder = await trip.driver()
    a, _ = await trip.assign(await trip.incident(), owner)
    await trip.ready()
    a_id = a.assignment_id
    r = await api.post(a_url(a_id, action), json=body, headers=intruder)
    assert r.status_code == 403
    assert (await db_session.get(Assignment, a_id)).status == "approved"


# ---------------------------------------------------------------- the driver's current assignment
async def test_current_assignment_is_what_the_driver_app_shows(api, trip, db_session) -> None:
    driver, headers = await trip.driver()
    assert (await api.get("/api/v1/driver/assignments/current", headers=headers)).status_code == 204
    hospital = Hospital(name="SIMULATED Civil Hospital Sukkur", location=pt(27.70, 68.86))
    db_session.add(hospital)
    inc = await trip.incident()
    await db_session.flush()
    a, v = await trip.assign(inc, driver, hospital_id=hospital.hospital_id)
    db_session.add(Recommendation(incident_id=inc.incident_id, vehicle_id=v.vehicle_id, rank=1, eta_seconds=240,
                                  distance_meters=2000, vehicle_type="ambulance", eta_is_approximate=True))
    await trip.ready()
    r = await api.get("/api/v1/driver/assignments/current", headers=headers)
    assert r.status_code == 200
    out = DriverAssignmentOut.model_validate(r.json())
    assert out.assignment_id == a.assignment_id and out.reference_no.startswith("INC-")
    assert (out.incident_type, out.severity, out.patients) == ("accident", "high", 3)
    assert out.location.source == "gps" and out.location.text == "near Clock Tower"
    assert (out.eta_seconds, out.eta_is_approximate) == (240, True)
    assert out.hospital and out.hospital.name == "SIMULATED Civil Hospital Sukkur"


async def test_a_finished_assignment_is_no_longer_current(api, trip) -> None:
    driver, headers = await trip.driver()
    await trip.assign(await trip.incident(), driver, status="completed", vehicle_status="available")
    await trip.ready()
    assert (await api.get("/api/v1/driver/assignments/current", headers=headers)).status_code == 204


# ---------------------------------------------------------------- dispatcher: cancel and hospital
async def test_cancel_frees_the_vehicle_and_hands_the_incident_back(api, trip, dispatcher, db_session) -> None:
    driver, _ = await trip.driver()
    inc = await trip.incident()
    a, v = await trip.assign(inc, driver, status="accepted")
    await trip.ready()
    r = await api.post(f"/api/v1/assignments/{a.assignment_id}/cancel", json={"reason": "SIMULATED: wrong vehicle"}, headers=dispatcher)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    await db_session.refresh(v)
    await db_session.refresh(inc)
    assert v.status == "available" and inc.status == "needs_check" and "vehicle_cancelled" in inc.review_reasons
    assert "assignment.cancelled" in await actions(db_session, inc.incident_id)


async def test_cancel_without_a_body_and_a_closed_one_cannot_be_cancelled(api, trip, dispatcher) -> None:
    driver, _ = await trip.driver()
    a, _ = await trip.assign(await trip.incident(), driver)
    done, _ = await trip.assign(await trip.incident(), (await trip.driver())[0], status="completed", vehicle_status="available")
    await trip.ready()
    a_id, done_id = a.assignment_id, done.assignment_id
    assert (await api.post(f"/api/v1/assignments/{a_id}/cancel", headers=dispatcher)).status_code == 200
    r = await api.post(f"/api/v1/assignments/{done_id}/cancel", headers=dispatcher)
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"
    assert (await api.post("/api/v1/assignments/987654/cancel", headers=dispatcher)).status_code == 404


async def test_cancel_after_another_vehicle_finished_closes_the_incident(api, trip, dispatcher, db_session) -> None:
    inc = await trip.incident(status="on_scene")
    await trip.assign(inc, (await trip.driver())[0], status="completed", vehicle_status="available")
    open_a, _ = await trip.assign(inc, (await trip.driver())[0])
    await trip.ready()
    assert (await api.post(f"/api/v1/assignments/{open_a.assignment_id}/cancel", headers=dispatcher)).status_code == 200
    await db_session.refresh(inc)
    assert inc.status == "closed"


async def test_hospital_change(api, trip, dispatcher, db_session) -> None:
    h1, h2 = Hospital(name="SIMULATED Hospital A", location=pt(27.7, 68.86)), Hospital(name="SIMULATED Hospital B", location=pt(27.71, 68.87))
    gone = Hospital(name="SIMULATED closed", location=pt(27.7, 68.85), is_active=False)
    db_session.add_all([h1, h2, gone])
    await db_session.flush()
    driver, _ = await trip.driver()
    inc = await trip.incident()
    a, _ = await trip.assign(inc, driver, status="accepted", hospital_id=h1.hospital_id)
    done, _ = await trip.assign(inc, (await trip.driver())[0], status="completed", vehicle_status="available")
    await trip.ready()
    a_id, h2_id, gone_id, done_id = a.assignment_id, h2.hospital_id, gone.hospital_id, done.assignment_id
    r = await api.patch(f"/api/v1/assignments/{a_id}/hospital", json={"hospital_id": h2_id}, headers=dispatcher)
    assert r.status_code == 200 and r.json()["hospital_id"] == h2_id
    [audit] = (await db_session.scalars(select(AuditLog).where(AuditLog.action == "assignment.hospital_changed"))).all()
    assert (audit.details["from"], audit.details["to"]) == (h1.hospital_id, h2_id)
    assert (await api.patch(f"/api/v1/assignments/{a_id}/hospital", json={"hospital_id": gone_id}, headers=dispatcher)).status_code == 404
    r = await api.patch(f"/api/v1/assignments/{done_id}/hospital", json={"hospital_id": h2_id}, headers=dispatcher)
    assert r.status_code == 409


async def test_drivers_cannot_cancel_or_change_hospitals(api, trip) -> None:
    driver, headers = await trip.driver()
    a, _ = await trip.assign(await trip.incident(), driver)
    await trip.ready()
    assert (await api.post(f"/api/v1/assignments/{a.assignment_id}/cancel", headers=headers)).status_code == 403
    assert (await api.patch(f"/api/v1/assignments/{a.assignment_id}/hospital", json={"hospital_id": 1}, headers=headers)).status_code == 403


# ---------------------------------------------------------------- hospitals
async def test_hospital_list_has_only_active_ones_with_positions(api, trip, dispatcher, db_session) -> None:
    db_session.add_all([Hospital(name="SIMULATED Z Hospital", location=pt(27.70, 68.86)),
                        Hospital(name="SIMULATED closed one", location=pt(27.70, 68.86), is_active=False)])
    await db_session.flush()
    driver, driver_headers = await trip.driver()
    await trip.ready()
    for headers in (dispatcher, driver_headers):
        rows = (await api.get("/api/v1/hospitals", headers=headers)).json()
        names = [h["name"] for h in rows]
        assert "SIMULATED Z Hospital" in names and "SIMULATED closed one" not in names
        z = next(h for h in rows if h["name"] == "SIMULATED Z Hospital")
        assert (round(z["lat"], 2), round(z["lon"], 2)) == (27.70, 68.86)


async def test_trip_steps_need_an_accepted_assignment_even_if_the_vehicle_status_is_wrong(api, trip, db_session) -> None:
    driver, headers = await trip.driver()
    a, _ = await trip.assign(await trip.incident(), driver, status="approved", vehicle_status="en_route")  # inconsistent data
    await trip.ready()
    a_id = a.assignment_id
    r = await api.post(a_url(a_id, "status"), json={"status": "on_scene"}, headers=headers)
    assert r.status_code == 409 and r.json()["details"]["status"] == "approved"
    assert (await db_session.get(Assignment, a_id)).on_scene_at is None
