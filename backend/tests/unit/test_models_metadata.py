"""Schema v1 checks that need no database (B1-A1-07…11): the models define exactly the SDS tables, and
every allowed-values CHECK is built from the C-1 vocabulary."""
import re

import pytest
from sqlalchemy import CheckConstraint, DateTime

import app.models  # noqa: F401
from app.core.db import Base
from app.schemas import enums
from app.schemas.auth import UserRole

SDS_TABLES = {  # SDS v1.1 Tables 5.1–5.15
    "callers", "incidents", "incident_groups", "users", "vehicles", "vehicle_locations", "recommendations",
    "assignments", "hospitals", "audit_logs", "settings", "duplicate_candidates", "confirmation_requests",
    "user_sessions", "worker_heartbeats",
}
VOCABULARY = {
    ("incidents", "channel"): enums.Channel, ("incidents", "status"): enums.IncidentStatus,
    ("incidents", "incident_type"): enums.IncidentType, ("incidents", "severity"): enums.Severity,
    ("incidents", "trust_tier"): enums.TrustTier, ("incidents", "location_source"): enums.LocationSource,
    ("incidents", "pipeline_state"): enums.PipelineState, ("vehicles", "vehicle_type"): enums.VehicleType,
    ("vehicles", "status"): enums.VehicleStatus, ("recommendations", "vehicle_type"): enums.VehicleType,
    ("assignments", "status"): enums.AssignmentStatus, ("duplicate_candidates", "decision"): enums.DuplicateDecision,
    ("users", "role"): UserRole,
}


def allowed(table: str, column: str) -> set[str]:
    for c in Base.metadata.tables[table].constraints:
        if isinstance(c, CheckConstraint):
            m = re.fullmatch(rf"{column} IN \((.*)\)", str(c.sqltext))
            if m:
                return set(re.findall(r"'([^']*)'", m.group(1)))
    raise AssertionError(f"no allowed-values CHECK on {table}.{column}")


def test_models_define_exactly_the_sds_tables() -> None:
    assert set(Base.metadata.tables) == SDS_TABLES


@pytest.mark.parametrize(("table", "column"), sorted(VOCABULARY), ids=lambda x: str(x))
def test_check_constraints_use_the_c1_vocabulary(table: str, column: str) -> None:
    assert allowed(table, column) == {v.value for v in VOCABULARY[(table, column)]}


def test_every_timestamp_column_is_timezone_aware() -> None:
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, DateTime):
                assert col.type.timezone, f"{table.name}.{col.name}"


def test_constraint_names_follow_the_naming_convention() -> None:
    for table in Base.metadata.tables.values():
        for c in table.constraints:
            assert c.name, f"unnamed constraint on {table.name}"
