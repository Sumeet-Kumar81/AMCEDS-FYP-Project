"""Policy tests (B1-A2-07): SRS Table 7.3.2 truth table; high/critical/unknown never held back; D-021."""
import itertools

import pytest

from app.agents.policy import allocate_now, decide_action, is_urgent
from app.schemas.ai import TrustAction
from app.schemas.enums import Severity, TrustTier

TABLE = {
    ("high", "low"): "continue", ("high", "medium"): "continue", ("high", "high"): "continue", ("high", "critical"): "continue",
    ("medium", "low"): "continue_and_confirm", ("medium", "medium"): "continue_and_confirm",
    ("medium", "high"): "continue_and_confirm", ("medium", "critical"): "continue_and_confirm",
    ("low", "low"): "review_queue", ("low", "medium"): "review_queue",
    ("low", "high"): "urgent_with_warning", ("low", "critical"): "urgent_with_warning",
}


@pytest.mark.parametrize(("tier", "severity"), sorted(TABLE))
def test_srs_table_7_3_2(tier: str, severity: str) -> None:
    assert decide_action(tier, severity) == TABLE[(tier, severity)]


@pytest.mark.parametrize(("tier", "severity"), list(itertools.product(TrustTier, [Severity.HIGH, Severity.CRITICAL, None])))
def test_urgent_or_unknown_severity_is_never_held_back(tier: TrustTier, severity: Severity | None) -> None:
    """Safety rule 3 (property over every tier): never the review queue, always vehicles at once."""
    action = decide_action(tier, severity)
    assert action is not TrustAction.REVIEW_QUEUE and allocate_now(action)


def test_unknown_severity_counts_as_urgent() -> None:
    assert is_urgent(None) and decide_action("low", None) is TrustAction.URGENT_WITH_WARNING


@pytest.mark.parametrize("action", list(TrustAction))
def test_d021_only_the_review_queue_waits_for_vehicles(action: TrustAction) -> None:
    assert allocate_now(action) is (action is not TrustAction.REVIEW_QUEUE)


def test_bad_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        decide_action("very_low", "high")
    with pytest.raises(ValueError):
        decide_action("low", "urgent")
