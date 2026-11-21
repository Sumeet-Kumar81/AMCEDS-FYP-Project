"""Settings service tests (B1-A1-12): SRS Appendix C defaults, range checks, cross-field rules, TC-36."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Setting, User
from app.services import settings as svc
from app.services.settings import REGISTRY, SettingError

pytestmark = pytest.mark.db

MIGRATION_0003 = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0003_seed_settings.py"


async def admin(session: AsyncSession) -> int:
    user = User(full_name="SIMULATED Admin", username="admin_settings_test", password_hash="x", role="admin")
    session.add(user)
    await session.flush()
    return user.user_id


async def audit_count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "settings.changed"))


# ---------------------------------------------------------------- defaults
def test_srs_appendix_c_defaults() -> None:
    expected = {
        "patients_per_ambulance": 2, "spare_vehicles": 2, "dup_distance_m": 300, "dup_window_min": 15,
        "dup_auto_link": 85, "dup_possible": 60, "triage_min_confidence": 60, "trust_start": 50,
        "trust_tier_high": 70, "trust_tier_medium": 40, "trust_pts_real_history": 15, "trust_pts_fake_each": -30,
        "trust_pts_fake_floor": -60, "trust_pts_gps_match": 15, "trust_gps_match_m": 500, "trust_pts_gps_far": -20,
        "trust_gps_far_m": 2000, "trust_pts_one_nearby": 15, "trust_pts_two_nearby": 25,
        "trust_pts_real_details": 10, "trust_pts_vague": -15, "trust_pts_flood": -20,
        "assignment_timeout_s": 60, "signal_lost_s": 60, "geofence_m": 100, "idle_logout_min": 30,
        "lockout_attempts": 5, "lockout_min": 15,
    }
    assert {k: svc.defaults()[k] for k in expected} == expected


def test_decided_defaults_d022_d033() -> None:
    d = svc.defaults()
    assert (d["rate_limit_reports"], d["rate_limit_window_min"], d["rate_limit_block_min"]) == (5, 10, 10)
    assert (d["dup_weight_distance"], d["dup_weight_time"], d["dup_weight_meaning"]) == (0.4, 0.2, 0.4)


def test_every_default_is_inside_its_own_range() -> None:
    for spec in REGISTRY.values():
        assert spec.parse(spec.default) == spec.default


def test_migration_0003_holds_exactly_the_registry_defaults() -> None:
    module_spec = importlib.util.spec_from_file_location("m0003", MIGRATION_0003)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    assert dict(module.DEFAULTS) == {k: str(v) for k, v in svc.defaults().items()}


async def test_migration_seeded_every_key(db_session: AsyncSession) -> None:
    stored = dict((await db_session.execute(select(Setting.setting_key, Setting.setting_value))).all())
    assert set(stored) == set(REGISTRY)
    assert await svc.get_all(db_session) == svc.defaults()


async def test_snapshot_contains_every_key(db_session: AsyncSession) -> None:
    assert set(await svc.get_snapshot(db_session)) == set(REGISTRY)


# ---------------------------------------------------------------- changes (UC-12)
async def test_valid_change_is_stored_and_audited(db_session: AsyncSession) -> None:
    user_id = await admin(db_session)
    assert await svc.update(db_session, "dup_distance_m", "450", user_id=user_id) == 450
    assert (await svc.get_all(db_session))["dup_distance_m"] == 450
    row = await db_session.scalar(select(AuditLog).where(AuditLog.action == "settings.changed"))
    assert row.user_id == user_id and row.details == {"changes": {"dup_distance_m": {"old": 300, "new": 450}}}


@pytest.mark.parametrize("key,value", [
    ("dup_auto_link", 150), ("dup_auto_link", "abc"), ("patients_per_ambulance", 0),
    ("patients_per_ambulance", "2.5"), ("patients_per_ambulance", True), ("dup_weight_time", "nan"),
    ("dup_possible", 90),  # must stay below dup_auto_link (85)
    ("trust_tier_medium", 75),  # must stay below trust_tier_high (70)
    ("dup_weight_time", 0.3),  # the three weights would add up to 1.1
    ("made_up_key", 1),
])
async def test_invalid_change_rejected_and_old_value_kept(db_session: AsyncSession, key: str, value) -> None:
    """TC-36: an out-of-range or rule-breaking value is rejected and the old value stays in force."""
    user_id = await admin(db_session)
    before, audits = await svc.get_all(db_session), await audit_count(db_session)
    with pytest.raises(SettingError):
        await svc.update(db_session, key, value, user_id=user_id)
    assert await svc.get_all(db_session) == before
    assert await audit_count(db_session) == audits


async def test_values_that_must_change_together_can(db_session: AsyncSession) -> None:
    user_id = await admin(db_session)
    changed = await svc.update_many(db_session, {"dup_weight_distance": "0.5", "dup_weight_time": "0.1"}, user_id=user_id)
    assert changed == {"dup_weight_distance": 0.5, "dup_weight_time": 0.1}
    assert await audit_count(db_session) == 1


async def test_raising_both_duplicate_thresholds_together(db_session: AsyncSession) -> None:
    user_id = await admin(db_session)
    await svc.update_many(db_session, {"dup_auto_link": 95, "dup_possible": 88}, user_id=user_id)
    values = await svc.get_all(db_session)
    assert (values["dup_auto_link"], values["dup_possible"]) == (95, 88)


async def test_a_broken_stored_value_is_reported_not_hidden(db_session: AsyncSession) -> None:
    await db_session.execute(text("UPDATE settings SET setting_value = 'lots' WHERE setting_key = 'geofence_m'"))
    with pytest.raises(SettingError):
        await svc.get_all(db_session)


async def test_missing_key_falls_back_to_default(db_session: AsyncSession) -> None:
    await db_session.execute(text("DELETE FROM settings WHERE setting_key = 'geofence_m'"))
    assert (await svc.get_all(db_session))["geofence_m"] == 100
