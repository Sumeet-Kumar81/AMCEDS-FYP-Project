"""C-1 vocabularies must match decision D-005 exactly (a changed value is a contract change)."""
from enum import StrEnum

import pytest

from app.schemas import enums

EXPECTED: dict[type[StrEnum], list[str]] = {
    enums.Channel: ["voice", "sms", "web", "app"],
    enums.IncidentStatus: ["new", "triaged", "needs_check", "dispatched", "on_scene", "closed", "fake"],
    enums.IncidentType: ["accident", "fire", "medical", "other"],
    enums.Severity: ["low", "medium", "high", "critical"],
    enums.TrustTier: ["high", "medium", "low"],
    enums.LocationSource: ["gps", "text", "unknown"],
    enums.VehicleType: ["ambulance", "fire_truck", "backup"],
    enums.VehicleStatus: [
        "available", "assigned", "en_route", "on_scene", "transporting", "at_hospital", "offline",
    ],
    enums.AssignmentStatus: ["approved", "accepted", "declined", "timed_out", "completed", "cancelled"],
    enums.PipelineState: ["pending", "processing", "done", "failed", "reallocate"],
    enums.DuplicateDecision: ["auto_linked", "possible", "confirmed", "rejected", "separate"],
}


@pytest.mark.parametrize("enum_cls", list(EXPECTED), ids=lambda c: c.__name__)
def test_values_match_decision_d005(enum_cls: type[StrEnum]) -> None:
    assert [m.value for m in enum_cls] == EXPECTED[enum_cls]


def test_every_enum_in_the_module_is_covered() -> None:
    defined = {
        obj for obj in vars(enums).values()
        if isinstance(obj, type) and issubclass(obj, StrEnum) and obj is not StrEnum
    }
    assert defined == set(EXPECTED), "a new enum was added without an expected-values test"


def test_members_behave_as_plain_strings() -> None:
    assert enums.Channel.APP == "app"
    assert str(enums.Severity.CRITICAL) == "critical"


def test_old_channel_name_mobile_is_not_a_member() -> None:
    with pytest.raises(ValueError):
        enums.Channel("mobile")
