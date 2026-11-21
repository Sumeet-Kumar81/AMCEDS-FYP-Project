"""Settings service (B1-A1-12): the admin-configurable business rules of SRS Appendix C.

* ``REGISTRY`` is the single list of settings: key, type, default, allowed range and source.
  Migration 0003 stores every default in the ``settings`` table; the admin changes values with
  ``update``. A key missing from the table falls back to its default.
* ``update`` validates type, range and the cross-field rules; an invalid value raises
  ``SettingError`` and the old value is kept (SRS UC-12, TC-36). Every change is audited.
* ``get_snapshot`` returns every value; intake stores it in ``incidents.settings_snapshot`` so new
  settings apply to new incidents only (UC-12).

Decisions behind some defaults (DECISIONS_LOG): D-022 report flood limit, D-033 duplicate weights.
``fallback_speed_kmh`` (straight-line ETA when routing is down) has no value in the SRS; 40 km/h is
the developer's assumption and can be changed by the admin.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import Setting
from app.services.audit import AuditAction, record

logger = logging.getLogger(__name__)

Value = int | float


class SettingError(ValueError):
    """The value is unknown, of the wrong type, out of range or breaks a cross-field rule."""


@dataclass(frozen=True)
class SettingSpec:
    key: str
    kind: type[int] | type[float]
    default: Value
    minimum: Value
    maximum: Value
    description: str
    source: str

    def parse(self, raw: str | int | float) -> Value:
        """Convert and range-check one value (cross-field rules are checked separately)."""
        if isinstance(raw, bool):
            raise SettingError(f"{self.key}: a number is required")
        value: Value
        if self.kind is int:
            if isinstance(raw, int):
                value = raw
            elif isinstance(raw, float) and raw.is_integer():
                value = int(raw)
            elif isinstance(raw, str) and re.fullmatch(r"\s*-?\d+\s*", raw):
                value = int(raw)
            else:
                raise SettingError(f"{self.key}: '{raw}' is not a whole number")
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                raise SettingError(f"{self.key}: '{raw}' is not a number") from None
            if not math.isfinite(value):
                raise SettingError(f"{self.key}: must be a finite number")
        if not (self.minimum <= value <= self.maximum):
            raise SettingError(f"{self.key}: {value} is outside the allowed range {self.minimum}–{self.maximum}")
        return value


def _spec(key: str, kind: type, default: Value, lo: Value, hi: Value, description: str, source: str) -> SettingSpec:
    return SettingSpec(key, kind, default, lo, hi, description, source)


REGISTRY: dict[str, SettingSpec] = {s.key: s for s in [
    # vehicles (SRS Table 7.3.3)
    _spec("patients_per_ambulance", int, 2, 1, 6, "Patients one ambulance is counted for", "SRS Table 7.3.3"),
    _spec("spare_vehicles", int, 2, 0, 5, "Spare vehicles added to the ranked list", "SRS Table 7.3.3"),
    # duplicates (SRS Table 7.3.4; weights D-033)
    _spec("dup_distance_m", int, 300, 50, 2000, "Compare reports within this distance (m)", "SRS Table 7.3.4"),
    _spec("dup_window_min", int, 15, 1, 120, "Compare reports within this time (min)", "SRS Table 7.3.4"),
    _spec("dup_auto_link", int, 85, 60, 100, "Match confidence for automatic linking", "SRS Table 7.3.4"),
    _spec("dup_possible", int, 60, 30, 95, "Match confidence for 'possible duplicate'", "SRS Table 7.3.4"),
    _spec("dup_weight_distance", float, 0.4, 0.0, 1.0, "Weight of distance in the match score", "D-033"),
    _spec("dup_weight_time", float, 0.2, 0.0, 1.0, "Weight of time in the match score", "D-033"),
    _spec("dup_weight_meaning", float, 0.4, 0.0, 1.0, "Weight of text meaning in the match score", "D-033"),
    # triage (SRS Table 7.3.4)
    _spec("triage_min_confidence", int, 60, 0, 100, "Below this AI confidence (%) the dispatcher must check", "SRS Table 7.3.4"),
    # trust score (SRS Appendix C, Table 7.3.1)
    _spec("trust_start", int, 50, 0, 100, "Trust score before any signal", "SRS Appendix C"),
    _spec("trust_tier_high", int, 70, 1, 100, "Score at or above which the tier is high", "SRS Appendix C"),
    _spec("trust_tier_medium", int, 40, 0, 99, "Score at or above which the tier is medium", "SRS Appendix C"),
    _spec("trust_pts_real_history", int, 15, -100, 100, "Earlier reports confirmed real", "SRS Table 7.3.1"),
    _spec("trust_pts_fake_each", int, -30, -100, 0, "For each earlier report marked fake", "SRS Table 7.3.1"),
    _spec("trust_pts_fake_floor", int, -60, -100, 0, "Lowest total for earlier fake reports", "SRS Table 7.3.1"),
    _spec("trust_pts_gps_match", int, 15, -100, 100, "Caller GPS near the place in the message", "SRS Table 7.3.1"),
    _spec("trust_gps_match_m", int, 500, 10, 5000, "Distance counted as 'near' (m)", "SRS Table 7.3.1"),
    _spec("trust_pts_gps_far", int, -20, -100, 100, "Caller GPS far from the place in the message", "SRS Table 7.3.1"),
    _spec("trust_gps_far_m", int, 2000, 100, 50000, "Distance counted as 'far' (m)", "SRS Table 7.3.1"),
    _spec("trust_pts_one_nearby", int, 15, -100, 100, "One other independent report nearby", "SRS Table 7.3.1"),
    _spec("trust_pts_two_nearby", int, 25, -100, 100, "Two or more other independent reports nearby", "SRS Table 7.3.1"),
    _spec("trust_pts_real_details", int, 10, -100, 100, "The message has real details", "SRS Table 7.3.1"),
    _spec("trust_pts_vague", int, -15, -100, 100, "The message is vague or joking", "SRS Table 7.3.1"),
    _spec("trust_pts_flood", int, -20, -100, 100, "The device sent many reports in a short time", "SRS Table 7.3.1"),
    # report flood protection (D-022)
    _spec("rate_limit_reports", int, 5, 1, 100, "Reports allowed per device or phone in the window", "D-022"),
    _spec("rate_limit_window_min", int, 10, 1, 120, "Window for the report limit (min)", "D-022"),
    _spec("rate_limit_block_min", int, 10, 1, 1440, "Block time after the limit is passed (min)", "D-022"),
    # timers and distances (SRS Appendix C)
    _spec("assignment_timeout_s", int, 60, 10, 600, "Time for the driver to answer an assignment (s)", "SRS Appendix C / UC-08"),
    _spec("signal_lost_s", int, 60, 10, 600, "No GPS for this long = lost signal (s)", "SRS Appendix C / UC-10"),
    _spec("geofence_m", int, 100, 10, 1000, "Distance that counts as arrived (m)", "SRS Appendix C / UC-09"),
    _spec("idle_logout_min", int, 30, 5, 240, "Idle time before logout (min)", "SRS NFR-C4 / D-023"),
    _spec("lockout_attempts", int, 5, 1, 20, "Wrong passwords before the account locks", "SRS Appendix C / UC-11"),
    _spec("lockout_min", int, 15, 1, 1440, "Lock time after too many wrong passwords (min)", "SRS Appendix C / UC-11"),
    _spec("fallback_speed_kmh", int, 40, 5, 120, "Speed for straight-line ETA when routing is down (assumption)", "developer assumption"),
]}


def defaults() -> dict[str, Value]:
    return {key: spec.default for key, spec in REGISTRY.items()}


def check_cross_rules(values: dict[str, Value]) -> None:
    """Rules that involve more than one setting. Raises SettingError."""
    if not values["dup_possible"] < values["dup_auto_link"]:
        raise SettingError("dup_possible must be lower than dup_auto_link")
    if not values["trust_tier_medium"] < values["trust_tier_high"]:
        raise SettingError("trust_tier_medium must be lower than trust_tier_high")
    weights = values["dup_weight_distance"] + values["dup_weight_time"] + values["dup_weight_meaning"]
    if not math.isclose(weights, 1.0, abs_tol=1e-9):
        raise SettingError(f"the three duplicate weights must add up to 1 (now {weights:g})")
    if not values["trust_gps_match_m"] < values["trust_gps_far_m"]:
        raise SettingError("trust_gps_match_m must be lower than trust_gps_far_m")
    if not values["trust_pts_fake_floor"] <= values["trust_pts_fake_each"]:
        raise SettingError("trust_pts_fake_floor must not be above trust_pts_fake_each")


def spec_for(key: str) -> SettingSpec:
    try:
        return REGISTRY[key]
    except KeyError:
        raise SettingError(f"unknown setting '{key}'") from None


async def get_all(session: AsyncSession) -> dict[str, Value]:
    """Every setting: the stored value, or the default if the key is not stored. Unknown stored keys
    are ignored (and logged); an invalid stored value raises, it is never silently replaced."""
    values = defaults()
    for key, raw in (await session.execute(select(Setting.setting_key, Setting.setting_value))).all():
        if key not in REGISTRY:
            logger.warning("ignoring unknown stored setting %s", key)
            continue
        values[key] = REGISTRY[key].parse(raw)
    return values


async def get_value(session: AsyncSession, key: str) -> Value:
    """One setting: the stored value, or its default if not stored."""
    spec = spec_for(key)
    raw = await session.scalar(select(Setting.setting_value).where(Setting.setting_key == key))
    return spec.default if raw is None else spec.parse(raw)


async def get_snapshot(session: AsyncSession) -> dict[str, Value]:
    """All values in force now, for ``incidents.settings_snapshot``."""
    return await get_all(session)


async def update_many(session: AsyncSession, changes: dict[str, str | int | float], *, user_id: int) -> dict[str, Value]:
    """Validate and store several settings together (UC-12). Does not commit; the caller commits.

    The cross-field rules are checked on the combined result, so values that must change together
    (for example the three duplicate weights, which must add up to 1) can be changed in one call.
    On any error nothing is written and the old values stay in force (TC-36).
    """
    if not changes:
        raise SettingError("no settings to change")
    parsed = {key: spec_for(key).parse(raw) for key, raw in changes.items()}
    current = await get_all(session)
    check_cross_rules({**current, **parsed})
    for key, new_value in parsed.items():
        await session.execute(
            insert(Setting)
            .values(setting_key=key, setting_value=str(new_value), updated_by=user_id)
            .on_conflict_do_update(
                index_elements=[Setting.setting_key],
                set_={"setting_value": str(new_value), "updated_by": user_id, "updated_at": func.now()},
            )
        )
    await record(session, AuditAction.SETTINGS_CHANGED, user_id=user_id,
                 details={"changes": {k: {"old": current[k], "new": v} for k, v in parsed.items()}})
    logger.info("settings changed by user %s: %s", user_id, sorted(parsed))
    return parsed


async def update(session: AsyncSession, key: str, raw_value: str | int | float, *, user_id: int) -> Value:
    """Validate and store one setting; see ``update_many``."""
    return (await update_many(session, {key: raw_value}, user_id=user_id))[key]


check_cross_rules(defaults())  # the shipped defaults must satisfy their own rules
