"""Dispatch approval and the dispatcher's vehicle list (B1-A1-25): TC-21 (locked, dispatched, audit of AI
suggestion vs choice and approver), TC-46 (no token / wrong role → nothing created), refusals with the
next best vehicle, fake/closed never dispatched, urgent low-trust dispatchable. SIMULATED data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AuditLog, Hospital, Incident, Recommendation, User, Vehicle
from app.schemas.auth import UserRole

pytestmark = pytest.mark.db
SUKKUR = (27.7052, 68.8574)
NOW = datetime.now(timezone.utc)


def pt(lat: float, lon: float) -> WKTElement:
    return WKTElement(f"POINT({lon} {lat})", srid=4326)


class World:
    def __init__(self, db: AsyncSession, make_user) -> None:
        self.db, self.make_user = db, make_user
        self.n = 0

    async def vehicle(self, km: float = 1.0, *, vtype: str = "ambulance", on_duty: bool = True, driver: bool = True,
                      status: str = "available", seen_s: int = 5) -> Vehicle:
        self.n += 1
        driver_id = None
        if driver:
            d: User = await self.make_user(UserRole.DRIVER)
            d.on_duty = on_duty
            driver_id = d.user_id
        v = Vehicle(vehicle_type=vtype, plate_number=f"SIM-D-{self.n:03d}", driver_id=driver_id, status=status,
                    last_location=pt(SUKKUR[0] + km / 111.2, SUKKUR[1]), last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=seen_s))
        self.db.add(v)
        await self.db.flush()
        return v

    async def incident(self, *, status: str = "triaged", severity: str | None = "high", recs: list[Vehicle] = (),
                       trust_tier: str | None = "medium", location: bool = True) -> Incident:
        row = Incident(channel="web", original_text="SIMULATED: bus accident near Clock Tower", status=status,
                       severity=severity, trust_tier=trust_tier, location=pt(*SUKKUR) if location else None,
                       location_source="gps" if location else "unknown")
        self.db.add(row)
        await self.db.flush()
        for rank, v in enumerate(recs, start=1):
            self.db.add(Recommendation(incident_id=row.incident_id, vehicle_id=v.vehicle_id, rank=rank,
                                       eta_seconds=60 * rank, distance_meters=800 * rank, vehicle_type=v.vehicle_type,
                                       eta_is_approximate=True))
        await self.db.flush()
        return row

    async def ready(self) -> None:
        await self.db.commit()  # the route may roll back; keep the set-up data


@pytest.fixture
def world(db_session, make_user) -> World:
    return World(db_session, make_user)


@pytest.fixture
async def dispatcher(make_user, sign_in) -> tuple[User, dict[str, str]]:
    user = await make_user(UserRole.DISPATCHER)
    return user, await sign_in(user)


def url(incident: Incident) -> str:
    return f"/api/v1/incidents/{incident.incident_id}/dispatch"


async def count(db: AsyncSession, model) -> int:
    return await db.scalar(select(func.count()).select_from(model))


async def audits(db: AsyncSession, incident_id: int, action: str) -> list[AuditLog]:
    return list((await db.scalars(select(AuditLog).where(AuditLog.incident_id == incident_id, AuditLog.action == action)
                                  .order_by(AuditLog.log_id))).all())


# ---------------------------------------------------------------- TC-21: the approved dispatch
async def test_tc21_approval_locks_dispatches_and_audits_suggestion_vs_choice(api, world, dispatcher, db_session) -> None:
    user, headers = dispatcher
    v1, v2, v3 = await world.vehicle(1), await world.vehicle(2), await world.vehicle(3)
    inc = await world.incident(recs=[v1, v2, v3])
    await world.ready()
    r = await api.post(url(inc), json={"vehicle_ids": [v1.vehicle_id]}, headers=headers)
    assert r.status_code == 201, r.text
    [out] = r.json()
    assert (out["vehicle_id"], out["approved_by"], out["status"]) == (v1.vehicle_id, user.user_id, "approved")
    assert datetime.fromisoformat(out["approved_at"]) > NOW - timedelta(minutes=1)
    for obj in (inc, v1, v2):
        await db_session.refresh(obj)
    assert inc.status == "dispatched" and v1.status == "assigned" and v2.status == "available"
    [audit] = await audits(db_session, inc.incident_id, "dispatch.approved")
    assert audit.user_id == user.user_id
    d = audit.details
    assert d["recommended"] == [v1.vehicle_id, v2.vehicle_id, v3.vehicle_id] and d["selected"] == [v1.vehicle_id]
    assert d["same_as_ai"] is True and d["manual_mode"] is False and d["override_reason"] is None
    assert d["incident_status"] == {"from": "triaged", "to": "dispatched"}
    assert "not sent" in d["driver_alert"]  # honest: no driver alert exists yet
    locks = await audits(db_session, inc.incident_id, "vehicle.locked")
    assert [x.details["vehicle_id"] for x in locks] == [v1.vehicle_id]


async def test_several_vehicles_and_a_hospital(api, world, dispatcher, db_session) -> None:
    _, headers = dispatcher
    v1, v2 = await world.vehicle(1), await world.vehicle(2, vtype="fire_truck")
    hospital = Hospital(name="SIMULATED Civil Hospital", location=pt(27.70, 68.86))
    db_session.add(hospital)
    inc = await world.incident(recs=[v1])
    await world.ready()
    r = await api.post(url(inc), json={"vehicle_ids": [v2.vehicle_id, v1.vehicle_id], "hospital_id": hospital.hospital_id,
                                        "override_reason": "  SIMULATED: fire seen, fire truck too  "}, headers=headers)
    assert r.status_code == 201
    assert sorted(a["vehicle_id"] for a in r.json()) == sorted([v1.vehicle_id, v2.vehicle_id])
    assert {a["hospital_id"] for a in r.json()} == {hospital.hospital_id}
    [audit] = await audits(db_session, inc.incident_id, "dispatch.approved")
    assert audit.details["same_as_ai"] is False and audit.details["override_reason"] == "SIMULATED: fire seen, fire truck too"


async def test_manual_mode_when_there_is_no_recommendation(api, world, dispatcher, db_session) -> None:
    _, headers = dispatcher
    v = await world.vehicle(1)
    inc = await world.incident(status="needs_check", severity=None, location=False)  # e.g. AI failed
    await world.ready()
    assert (await api.post(url(inc), json={"vehicle_ids": [v.vehicle_id]}, headers=headers)).status_code == 201
    [audit] = await audits(db_session, inc.incident_id, "dispatch.approved")
    assert audit.details["manual_mode"] is True and audit.details["recommended"] == []


async def test_lost_gps_is_allowed_but_recorded(api, world, dispatcher, db_session) -> None:
    _, headers = dispatcher
    v = await world.vehicle(1, seen_s=600)
    inc = await world.incident(recs=[v])
    await world.ready()
    assert (await api.post(url(inc), json={"vehicle_ids": [v.vehicle_id]}, headers=headers)).status_code == 201
    [audit] = await audits(db_session, inc.incident_id, "dispatch.approved")
    assert audit.details["signal_lost"] == [v.vehicle_id]


# ---------------------------------------------------------------- never blocked by trust (rule 3), fake never sent (rule 5)
@pytest.mark.parametrize(("severity", "status"), [("critical", "needs_check"), ("low", "needs_check"), (None, "new")])
async def test_low_trust_and_unchecked_reports_can_be_dispatched_by_a_human(api, world, dispatcher, severity, status) -> None:
    _, headers = dispatcher
    v = await world.vehicle(1)
    inc = await world.incident(status=status, severity=severity, trust_tier="low")
    await world.ready()
    assert (await api.post(url(inc), json={"vehicle_ids": [v.vehicle_id]}, headers=headers)).status_code == 201


@pytest.mark.parametrize("status", ["fake", "closed"])
async def test_fake_or_closed_is_never_dispatched(api, world, dispatcher, db_session, status) -> None:
    _, headers = dispatcher
    v = await world.vehicle(1)
    inc = await world.incident(status=status, recs=[v])
    await world.ready()
    r = await api.post(url(inc), json={"vehicle_ids": [v.vehicle_id]}, headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "incident_not_dispatchable"
    await db_session.refresh(v)
    assert v.status == "available" and await count(db_session, Assignment) == 0


async def test_a_backup_can_be_sent_and_on_scene_stays_on_scene(api, world, dispatcher, db_session) -> None:
    _, headers = dispatcher
    v1, v2 = await world.vehicle(1), await world.vehicle(2)
    inc = await world.incident(recs=[v1, v2])
    await world.ready()
    assert (await api.post(url(inc), json={"vehicle_ids": [v1.vehicle_id]}, headers=headers)).status_code == 201
    inc.status = "on_scene"
    await db_session.commit()
    assert (await api.post(url(inc), json={"vehicle_ids": [v2.vehicle_id]}, headers=headers)).status_code == 201
    await db_session.refresh(inc)
    assert inc.status == "on_scene" and await count(db_session, Assignment) == 2


# ---------------------------------------------------------------- refusals with the next best (TC-22 part)
async def test_a_vehicle_with_an_open_assignment_is_refused_with_the_next_best(api, world, dispatcher, db_session, make_user) -> None:
    user, headers = dispatcher
    v1, v2, v3 = await world.vehicle(1), await world.vehicle(2), await world.vehicle(3)
    other = await world.incident(recs=[v1])
    inc = await world.incident(recs=[v1, v2, v3])
    db_session.add(Assignment(incident_id=other.incident_id, vehicle_id=v1.vehicle_id, approved_by=user.user_id))
    await world.ready()
    ids = (v1.vehicle_id, v2.vehicle_id, v3.vehicle_id)  # read before the request: a refusal rolls the session back
    r = await api.post(url(inc), json={"vehicle_ids": [ids[0]]}, headers=headers)
    assert r.status_code == 409
    assert r.json()["code"] == "vehicle_locked"
    assert r.json()["details"] == {"vehicle_ids": [ids[0]], "next_best": [ids[1], ids[2]]}
    await db_session.refresh(inc)
    assert inc.status == "triaged" and await count(db_session, Assignment) == 1


async def test_all_or_nothing_when_one_of_several_is_taken(api, world, dispatcher, db_session) -> None:
    user, headers = dispatcher
    v1, v2 = await world.vehicle(1), await world.vehicle(2)
    other = await world.incident()
    inc = await world.incident(recs=[v1, v2])
    db_session.add(Assignment(incident_id=other.incident_id, vehicle_id=v2.vehicle_id, approved_by=user.user_id))
    await world.ready()
    r = await api.post(url(inc), json={"vehicle_ids": [v1.vehicle_id, v2.vehicle_id]}, headers=headers)
    assert r.status_code == 409
    await db_session.refresh(v1)
    assert v1.status == "available" and await count(db_session, Assignment) == 1  # v1 not taken either


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"on_duty": False}, "driver_off_duty"),
    ({"driver": False}, "no_driver"),
    ({"status": "en_route"}, "status_en_route"),
    ({"status": "offline"}, "status_offline"),
])
async def test_a_vehicle_that_cannot_go_is_refused_with_the_reason(api, world, dispatcher, db_session, kwargs, reason) -> None:
    _, headers = dispatcher
    bad, good = await world.vehicle(1, **kwargs), await world.vehicle(2)
    inc = await world.incident(recs=[bad, good])
    await world.ready()
    bad_id, good_id = bad.vehicle_id, good.vehicle_id
    r = await api.post(url(inc), json={"vehicle_ids": [bad_id]}, headers=headers)
    assert r.status_code == 409 and r.json()["code"] == "vehicle_unavailable"
    assert r.json()["details"] == {"vehicles": [{"vehicle_id": bad_id, "reason": reason}], "next_best": [good_id]}
    assert await count(db_session, Assignment) == 0


async def test_unknown_incident_vehicle_or_hospital_is_404(api, world, dispatcher, db_session) -> None:
    _, headers = dispatcher
    v = await world.vehicle(1)
    inc = await world.incident()
    closed_h = Hospital(name="SIMULATED closed hospital", location=pt(27.7, 68.86), is_active=False)
    db_session.add(closed_h)
    await world.ready()
    vid, path, closed_id = v.vehicle_id, url(inc), closed_h.hospital_id
    r = await api.post("/api/v1/incidents/987654/dispatch", json={"vehicle_ids": [vid]}, headers=headers)
    assert r.status_code == 404 and r.json()["message"] == "No such incident."
    r = await api.post(path, json={"vehicle_ids": [vid, 987654]}, headers=headers)
    assert r.status_code == 404 and r.json()["details"] == {"vehicle_ids": [987654]}
    for hospital_id in (987654, closed_id):
        r = await api.post(path, json={"vehicle_ids": [vid], "hospital_id": hospital_id}, headers=headers)
        assert r.status_code == 404 and r.json()["details"] == {"hospital_id": hospital_id}
    assert await count(db_session, Assignment) == 0


@pytest.mark.parametrize("body", [{}, {"vehicle_ids": []}, {"vehicle_ids": [1, 1]}, {"vehicle_ids": list(range(1, 12))},
                                  {"vehicle_ids": [0]}, {"vehicle_ids": [1], "status": "dispatched"},
                                  {"vehicle_ids": [1], "override_reason": "x" * 501}])
async def test_bad_bodies_are_422(api, world, dispatcher, body) -> None:
    _, headers = dispatcher
    inc = await world.incident()
    await world.ready()
    r = await api.post(url(inc), json=body, headers=headers)
    assert r.status_code == 422 and r.json()["code"] == "validation_error"


# ---------------------------------------------------------------- TC-46: only an authenticated dispatcher
async def test_tc46_no_token_or_wrong_role_creates_nothing(api, world, make_user, sign_in, db_session) -> None:
    v = await world.vehicle(1)
    inc = await world.incident(recs=[v])
    await world.ready()
    assert (await api.post(url(inc), json={"vehicle_ids": [v.vehicle_id]})).status_code == 401
    for role in (UserRole.DRIVER, UserRole.ADMIN):
        r = await api.post(url(inc), json={"vehicle_ids": [v.vehicle_id]}, headers=await sign_in(await make_user(role)))
        assert r.status_code == 403
    await db_session.refresh(v)
    assert v.status == "available" and await count(db_session, Assignment) == 0
    assert await audits(db_session, inc.incident_id, "dispatch.approved") == []


# ---------------------------------------------------------------- GET /vehicles
async def test_vehicle_list_shows_who_can_go_and_why_not(api, world, dispatcher, db_session) -> None:
    user, headers = dispatcher
    ok = await world.vehicle(3)
    off = await world.vehicle(1, on_duty=False)
    lost = await world.vehicle(2, seen_s=900)
    busy = await world.vehicle(4)
    inc = await world.incident()
    db_session.add(Assignment(incident_id=inc.incident_id, vehicle_id=busy.vehicle_id, approved_by=user.user_id))
    await world.ready()
    rows = {v["vehicle_id"]: v for v in (await api.get("/api/v1/vehicles", headers=headers)).json()}
    assert rows[ok.vehicle_id]["can_dispatch"] is True and rows[ok.vehicle_id]["signal_lost"] is False
    assert rows[off.vehicle_id]["can_dispatch"] is False and rows[off.vehicle_id]["driver_on_duty"] is False
    assert rows[lost.vehicle_id]["can_dispatch"] is True and rows[lost.vehicle_id]["signal_lost"] is True  # warning only
    assert rows[busy.vehicle_id]["has_open_assignment"] is True and rows[busy.vehicle_id]["can_dispatch"] is False
    assert rows[ok.vehicle_id]["distance_meters"] is None and rows[ok.vehicle_id]["plate_number"].startswith("SIM-D-")


async def test_vehicle_list_near_an_incident_is_dispatchable_first_then_nearest(api, world, dispatcher) -> None:
    _, headers = dispatcher
    far, near, off_near = await world.vehicle(5), await world.vehicle(1), await world.vehicle(0.5, on_duty=False)
    inc = await world.incident()
    await world.ready()
    rows = (await api.get("/api/v1/vehicles", params={"incident_id": inc.incident_id}, headers=headers)).json()
    mine = [r for r in rows if r["vehicle_id"] in {far.vehicle_id, near.vehicle_id, off_near.vehicle_id}]
    assert [r["vehicle_id"] for r in mine] == [near.vehicle_id, far.vehicle_id, off_near.vehicle_id]
    assert 900 <= mine[0]["distance_meters"] <= 1100 and mine[0]["distance_is_approximate"] is True


async def test_vehicle_list_filters(api, world, dispatcher) -> None:
    _, headers = dispatcher
    amb, fire, off = await world.vehicle(1), await world.vehicle(2, vtype="fire_truck"), await world.vehicle(3, on_duty=False)
    await world.ready()
    ids = lambda r: {v["vehicle_id"] for v in r.json()}  # noqa: E731
    only_fire = ids(await api.get("/api/v1/vehicles", params={"type": "fire_truck"}, headers=headers))
    assert fire.vehicle_id in only_fire and amb.vehicle_id not in only_fire
    can = ids(await api.get("/api/v1/vehicles", params={"available_only": "true"}, headers=headers))
    assert {amb.vehicle_id, fire.vehicle_id} <= can and off.vehicle_id not in can


async def test_vehicle_list_is_for_dispatchers_only(api, make_user, sign_in) -> None:
    for role in (UserRole.DRIVER, UserRole.ADMIN):
        r = await api.get("/api/v1/vehicles", headers=await sign_in(await make_user(role)))
        assert r.status_code == 403


async def test_next_best_never_offers_a_vehicle_that_was_already_chosen(api, world, dispatcher) -> None:
    _, headers = dispatcher
    good, off, spare = await world.vehicle(1), await world.vehicle(2, on_duty=False), await world.vehicle(3)
    inc = await world.incident(recs=[good, off, spare])
    await world.ready()
    good_id, off_id, spare_id = good.vehicle_id, off.vehicle_id, spare.vehicle_id
    r = await api.post(url(inc), json={"vehicle_ids": [good_id, off_id]}, headers=headers)
    assert r.status_code == 409 and r.json()["details"]["next_best"] == [spare_id]  # not good_id again
