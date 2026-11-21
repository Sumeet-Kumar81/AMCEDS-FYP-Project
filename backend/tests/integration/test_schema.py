"""Schema v1 tests (B1-A1-07…11) on a throwaway database migrated to head. Each test runs in a
transaction that is rolled back. Data used here is SIMULATED."""
from __future__ import annotations

import re

import psycopg2
import pytest
from psycopg2 import errors

from app.schemas.assignment import OPEN_ASSIGNMENT_STATUSES
from app.schemas.incident import REFERENCE_NO_PATTERN
from tests.integration.conftest import query

pytestmark = pytest.mark.db

SUKKUR = (68.8574, 27.7052)  # lon, lat


def run(conn, statement: str, params: tuple | None = None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(statement, params)
        return cur.fetchall() if cur.description else []


def one(conn, statement: str, params: tuple | None = None):
    return run(conn, statement, params)[0][0]


def new_user(conn, username: str = "dispatcher1", role: str = "dispatcher") -> int:
    return one(conn, "INSERT INTO users (full_name, username, password_hash, role) VALUES (%s, %s, 'x', %s) "
               "RETURNING user_id", (f"SIMULATED {username}", username, role))


def new_vehicle(conn, plate: str = "SKR-001", lon: float = SUKKUR[0], lat: float = SUKKUR[1], **cols) -> int:
    keys = ["vehicle_type", "plate_number", "last_location", *cols]
    values = ["ambulance", plate, f"SRID=4326;POINT({lon} {lat})", *cols.values()]
    return one(conn, f"INSERT INTO vehicles ({', '.join(keys)}) VALUES ({', '.join(['%s'] * len(keys))}) "
               "RETURNING vehicle_id", tuple(values))


def new_incident(conn, text: str | None = "SIMULATED bus accident near the market", audio: str | None = None) -> int:
    return one(conn, "INSERT INTO incidents (channel, original_text, audio_ref) VALUES ('web', %s, %s) "
               "RETURNING incident_id", (text, audio))


def assign(conn, incident_id: int, vehicle_id: int, user_id: int, status: str = "approved") -> int:
    return one(conn, "INSERT INTO assignments (incident_id, vehicle_id, approved_by, status) VALUES (%s, %s, %s, %s) "
               "RETURNING assignment_id", (incident_id, vehicle_id, user_id, status))


# ---------------------------------------------------------------- reference number (NFR-P12)
def test_reference_number_is_computed_by_the_database(db) -> None:
    incident_id = new_incident(db)
    ref = one(db, "SELECT reference_no FROM incidents WHERE incident_id = %s", (incident_id,))
    assert ref == f"INC-{incident_id:06d}" and re.fullmatch(REFERENCE_NO_PATTERN, ref)
    one(db, "INSERT INTO incidents (incident_id, channel, original_text) VALUES (1234567, 'sms', 'x') RETURNING 1")
    assert one(db, "SELECT reference_no FROM incidents WHERE incident_id = 1234567") == "INC-1234567"


def test_reference_number_cannot_be_written_by_hand(db) -> None:
    with pytest.raises(errors.GeneratedAlways):
        run(db, "INSERT INTO incidents (channel, original_text, reference_no) VALUES ('web', 'x', 'INC-000000')")


def test_a_report_needs_text_or_audio(db) -> None:
    with pytest.raises(errors.CheckViolation, match="has_text_or_audio"):
        new_incident(db, text=None, audio=None)


def test_a_new_incident_gets_safe_defaults(db) -> None:
    row = run(db, "SELECT status, pipeline_state, location_source, review_reasons, settings_snapshot, received_at "
              "FROM incidents WHERE incident_id = %s", (new_incident(db),))[0]
    assert row[:5] == ("new", "pending", "unknown", [], {}) and row[5].tzinfo is not None


@pytest.mark.parametrize("column,value", [
    ("channel", "mobile"), ("status", "on scene"), ("severity", "urgent"), ("incident_type", "flood"),
    ("trust_tier", "very_high"), ("location_source", "guess"), ("pipeline_state", "retrust"),
    ("confidence", 1.5), ("confidence", -0.1), ("trust_score", 101), ("victims_estimate", -1),
])
def test_incident_values_outside_the_rules_are_rejected(db, column: str, value) -> None:
    incident_id = new_incident(db)
    with pytest.raises(errors.CheckViolation):
        run(db, f"UPDATE incidents SET {column} = %s WHERE incident_id = %s", (value, incident_id))


# ---------------------------------------------------------------- the caller's words never change
def test_original_text_cannot_be_changed(db) -> None:
    incident_id = new_incident(db)
    run(db, "UPDATE incidents SET status = 'triaged', severity = 'high' WHERE incident_id = %s", (incident_id,))
    with pytest.raises(errors.RaiseException, match="original_text cannot be changed"):
        run(db, "UPDATE incidents SET original_text = 'edited' WHERE incident_id = %s", (incident_id,))


def test_voice_report_gets_its_transcript_once_and_keeps_its_audio(db) -> None:
    incident_id = new_incident(db, text=None, audio="audio/SIMULATED-1.wav")
    run(db, "UPDATE incidents SET original_text = 'SIMULATED transcript' WHERE incident_id = %s", (incident_id,))
    run(db, "SAVEPOINT s")
    with pytest.raises(errors.RaiseException, match="original_text cannot be changed"):
        run(db, "UPDATE incidents SET original_text = 'second transcript' WHERE incident_id = %s", (incident_id,))
    run(db, "ROLLBACK TO SAVEPOINT s")
    with pytest.raises(errors.RaiseException, match="audio_ref cannot be changed"):
        run(db, "UPDATE incidents SET audio_ref = 'other.wav' WHERE incident_id = %s", (incident_id,))


# ---------------------------------------------------------------- double dispatch (NFR-S6) and human approval (NFR-S1)
def test_a_vehicle_cannot_have_two_open_assignments(db) -> None:
    user, vehicle = new_user(db), new_vehicle(db)
    first = assign(db, new_incident(db), vehicle, user)
    for status in ("approved", "accepted"):
        run(db, "SAVEPOINT s")
        with pytest.raises(errors.UniqueViolation, match="uq_assignments_open_vehicle"):
            assign(db, new_incident(db), vehicle, user, status)
        run(db, "ROLLBACK TO SAVEPOINT s")
    run(db, "UPDATE assignments SET status = 'completed' WHERE assignment_id = %s", (first,))
    assert assign(db, new_incident(db), vehicle, user)  # free again after completion


def test_open_statuses_in_the_index_equal_contract_c7(db) -> None:
    definition = one(db, "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_assignments_open_vehicle'")
    listed = set(re.findall(r"'(\w+)'", definition))
    assert listed == {s.value for s in OPEN_ASSIGNMENT_STATUSES}


def test_every_assignment_names_the_approving_dispatcher(db) -> None:
    with pytest.raises(errors.NotNullViolation):
        run(db, "INSERT INTO assignments (incident_id, vehicle_id, approved_by) VALUES (%s, %s, NULL)",
            (new_incident(db), new_vehicle(db)))


def test_assignment_status_vocabulary(db) -> None:
    with pytest.raises(errors.CheckViolation):
        assign(db, new_incident(db), new_vehicle(db), new_user(db), "on_scene")


# ---------------------------------------------------------------- audit log cannot be changed (NFR-C10)
@pytest.mark.parametrize("statement", [
    "UPDATE audit_logs SET action = 'edited'", "DELETE FROM audit_logs", "TRUNCATE audit_logs",
])
def test_audit_rows_cannot_be_changed_or_deleted(db, statement: str) -> None:
    run(db, "INSERT INTO audit_logs (action, details) VALUES ('ai.triage', '{\"suggested\": [5], \"chosen\": [5]}')")
    with pytest.raises(errors.RaiseException, match="audit_logs rows cannot be changed"):
        run(db, statement)


def test_audit_details_are_queryable_json(db) -> None:
    run(db, "INSERT INTO audit_logs (action, details) VALUES ('dispatch.approved', '{\"chosen\": [5, 8]}')")
    assert one(db, "SELECT details->'chosen' FROM audit_logs WHERE action = 'dispatch.approved'") == [5, 8]


# ---------------------------------------------------------------- users, callers, fleet
def test_username_unique_and_role_checked(db) -> None:
    new_user(db, "driver1", "driver")
    run(db, "SAVEPOINT s")
    with pytest.raises(errors.UniqueViolation):
        new_user(db, "driver1", "driver")
    run(db, "ROLLBACK TO SAVEPOINT s")
    with pytest.raises(errors.CheckViolation):
        new_user(db, "root1", "superuser")


def test_caller_phone_and_device_unique_only_when_present(db) -> None:
    run(db, "INSERT INTO callers (phone_number) VALUES (NULL), (NULL)")  # many callers without a phone
    run(db, "INSERT INTO callers (phone_number) VALUES ('+92-SIMULATED-1')")
    with pytest.raises(errors.UniqueViolation):
        run(db, "INSERT INTO callers (phone_number) VALUES ('+92-SIMULATED-1')")


def test_plate_unique_and_one_vehicle_per_driver(db) -> None:
    driver = new_user(db, "driver2", "driver")
    new_vehicle(db, "SKR-010", driver_id=driver)
    run(db, "SAVEPOINT s")
    with pytest.raises(errors.UniqueViolation):
        new_vehicle(db, "SKR-010")
    run(db, "ROLLBACK TO SAVEPOINT s")
    with pytest.raises(errors.UniqueViolation, match="uq_vehicles_driver_id"):
        new_vehicle(db, "SKR-011", driver_id=driver)


def test_geometry_round_trip(db) -> None:
    vehicle = new_vehicle(db)
    x, y, srid = run(db, "SELECT ST_X(last_location), ST_Y(last_location), ST_SRID(last_location) "
                     "FROM vehicles WHERE vehicle_id = %s", (vehicle,))[0]
    assert (round(x, 4), round(y, 4), srid) == (SUKKUR[0], SUKKUR[1], 4326)


def test_nearest_available_vehicle_within_5_km_uses_the_spatial_index(db) -> None:
    near = new_vehicle(db, "SKR-020", 68.8600, 27.7060)  # ~300 m away
    new_vehicle(db, "SKR-021", 68.9500, 27.7900)  # ~13 km away
    new_vehicle(db, "SKR-022", 68.8590, 27.7055, status="assigned")  # closest but busy
    sql = ("SELECT vehicle_id FROM vehicles WHERE status = 'available' "
           "AND ST_DWithin(last_location::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 5000) "
           "ORDER BY last_location <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)")
    assert [r[0] for r in run(db, sql, SUKKUR * 2)] == [near]
    run(db, "SET LOCAL enable_seqscan = off")
    plan = "\n".join(r[0] for r in run(db, "EXPLAIN " + sql, SUKKUR * 2))
    assert "idx_vehicles_last_location" in plan, plan


# ---------------------------------------------------------------- review tables
def test_duplicate_candidate_rules(db) -> None:
    a, b = new_incident(db), new_incident(db)
    run(db, "INSERT INTO duplicate_candidates (incident_id, candidate_incident_id, match_confidence, decision) "
        "VALUES (%s, %s, 72, 'possible')", (a, b))
    for bad in [(a, a, 90, "auto_linked"), (b, a, 101, "possible"), (b, a, 50, "maybe")]:
        run(db, "SAVEPOINT s")
        with pytest.raises(errors.CheckViolation):
            run(db, "INSERT INTO duplicate_candidates (incident_id, candidate_incident_id, match_confidence, decision) "
                "VALUES (%s, %s, %s, %s)", bad)
        run(db, "ROLLBACK TO SAVEPOINT s")


def test_confirmation_request_defaults_and_vocabulary(db) -> None:
    incident = new_incident(db)
    assert one(db, "INSERT INTO confirmation_requests (incident_id, channel, token_hash) VALUES (%s, 'sms', 'h') "
               "RETURNING response", (incident,)) == "none"
    with pytest.raises(errors.CheckViolation):
        run(db, "INSERT INTO confirmation_requests (incident_id, channel, token_hash) VALUES (%s, 'email', 'h')",
            (incident,))


# ---------------------------------------------------------------- relationships (SDS Table 2.2 + Table 5.x FKs)
EXPECTED_FKS = {
    ("incidents", "caller_id", "callers"), ("incidents", "group_id", "incident_groups"),
    ("recommendations", "incident_id", "incidents"), ("recommendations", "vehicle_id", "vehicles"),
    ("assignments", "incident_id", "incidents"), ("assignments", "vehicle_id", "vehicles"),
    ("assignments", "hospital_id", "hospitals"), ("assignments", "approved_by", "users"),
    ("vehicles", "driver_id", "users"), ("vehicle_locations", "vehicle_id", "vehicles"),
    ("audit_logs", "user_id", "users"), ("audit_logs", "incident_id", "incidents"),
    ("settings", "updated_by", "users"), ("duplicate_candidates", "incident_id", "incidents"),
    ("duplicate_candidates", "candidate_incident_id", "incidents"), ("duplicate_candidates", "decided_by", "users"),
    ("confirmation_requests", "incident_id", "incidents"), ("user_sessions", "user_id", "users"),
}


def test_foreign_keys_match_the_sds(schema_db: str) -> None:
    rows = query(schema_db, """
        SELECT tc.table_name, kcu.column_name, ccu.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    """)
    assert set(rows) == EXPECTED_FKS


def test_no_foreign_key_cascades_deletes(schema_db: str) -> None:
    """Records are never deleted through a cascade (users are disabled, audit rows are permanent)."""
    rules = query(schema_db, "SELECT DISTINCT delete_rule FROM information_schema.referential_constraints "
                  "WHERE constraint_schema = 'public'")
    assert {r[0] for r in rules} == {"NO ACTION"}


def test_every_timestamp_has_a_time_zone(schema_db: str) -> None:
    naive = query(schema_db, "SELECT table_name, column_name FROM information_schema.columns "
                  "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'")
    assert naive == []
