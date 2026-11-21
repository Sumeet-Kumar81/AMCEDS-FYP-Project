"""Trust Scorer tests (B1-A2-06): SRS Table 7.3.1 signal by signal, floor, clamping, tiers, TC-09, TC-11, D-035."""
import pytest

from app.agents.trust import DEFAULT_SETTINGS, TrustInputs, TrustScorer, signals_for, tier_for
from app.services.settings import defaults

scorer = TrustScorer()
NEUTRAL = TrustInputs(has_real_details=False, vague_or_joking=False)  # AI ran, nothing special


def score(**kw) -> int:
    return scorer.assess(TrustInputs(**{"has_real_details": False, "vague_or_joking": False, **kw}), "medium").score


def codes(**kw) -> dict[str, int]:
    return {s.code: s.points for s in signals_for(TrustInputs(**{"has_real_details": False, "vague_or_joking": False, **kw}))}


# ---------------------------------------------------------------- one test per signal (Table 7.3.1)
def test_start_is_50_and_no_history_is_neutral() -> None:
    """UC-03 1a: an unknown caller neither gains nor loses."""
    result = scorer.assess(NEUTRAL, "medium")
    assert result.score == 50 and result.signals == [] and result.tier == "medium"


@pytest.mark.parametrize(("kw", "code", "points"), [
    ({"real_count": 3}, "real_history", 15),
    ({"fake_count": 1}, "fake_history", -30),
    ({"distance_to_gps_m": 500}, "gps_match", 15),
    ({"distance_to_gps_m": 2001}, "gps_far", -20),
    ({"independent_nearby": 1}, "nearby_one", 15),
    ({"independent_nearby": 2}, "nearby_two_plus", 25),
    ({"independent_nearby": 7}, "nearby_two_plus", 25),
    ({"has_real_details": True}, "real_details", 10),
    ({"vague_or_joking": True}, "vague", -15),
    ({"device_flood": True}, "flood", -20),
])
def test_each_signal(kw: dict, code: str, points: int) -> None:
    assert codes(**kw) == {code: points}
    assert score(**kw) == 50 + points


def test_gps_between_500_m_and_2_km_gives_nothing() -> None:
    assert codes(distance_to_gps_m=1200) == {} and codes(distance_to_gps_m=2000) == {}


def test_fake_history_floor_is_minus_60() -> None:
    assert codes(fake_count=2) == {"fake_history": -60} and codes(fake_count=5) == {"fake_history": -60}


def test_every_point_has_a_reason() -> None:
    every = signals_for(TrustInputs(real_count=1, fake_count=1, distance_to_gps_m=10, independent_nearby=2,
                                    has_real_details=True, vague_or_joking=True, device_flood=True))
    assert len(every) == 7 and all(s.detail for s in every)  # GPS 'near' and 'far' exclude each other


# ---------------------------------------------------------------- clamping and tiers
def test_score_is_clamped_to_0_and_100() -> None:
    assert score(fake_count=3, distance_to_gps_m=5000, vague_or_joking=True, device_flood=True) == 0
    assert score(real_count=1, distance_to_gps_m=10, independent_nearby=3, has_real_details=True) == 100


@pytest.mark.parametrize(("value", "tier"), [(0, "low"), (39, "low"), (40, "medium"), (69, "medium"), (70, "high"), (100, "high")])
def test_tier_boundaries(value: int, tier: str) -> None:
    assert tier_for(value, DEFAULT_SETTINGS) == tier


# ---------------------------------------------------------------- SRS test cases
def test_tc09_two_earlier_fakes_make_the_report_low_trust() -> None:
    result = scorer.assess(TrustInputs(fake_count=2, has_real_details=False, vague_or_joking=False), "low")
    assert (result.score, result.tier, result.action) == (0, "low", "review_queue")


def test_tc11_gps_more_than_2_km_away_takes_20() -> None:
    assert codes(distance_to_gps_m=2500)["gps_far"] == -20


def test_low_trust_but_critical_is_urgent_not_held() -> None:
    result = scorer.assess(TrustInputs(fake_count=2, has_real_details=False, vague_or_joking=False), "critical")
    assert result.tier == "low" and result.action == "urgent_with_warning"


# ---------------------------------------------------------------- D-035 and settings
def test_d035_triage_unavailable_scores_the_other_signals_and_says_so() -> None:
    result = scorer.assess(TrustInputs(real_count=1, independent_nearby=1), None)
    assert {s.code: s.points for s in result.signals} == {"real_history": 15, "nearby_one": 15, "ai_unavailable": 0}
    assert result.score == 80 and result.action == "continue"  # never fake or held because the AI failed


def test_low_ai_confidence_is_not_an_input() -> None:
    assert "confidence" not in TrustInputs.__dataclass_fields__


def test_points_come_from_the_incidents_settings_snapshot() -> None:
    snapshot = {**defaults(), "trust_start": 60, "trust_pts_flood": -50, "trust_tier_high": 90}
    result = scorer.assess(TrustInputs(device_flood=True, has_real_details=False, vague_or_joking=False), "low", snapshot)
    assert result.score == 10 and result.tier == "low"


def test_result_is_a_valid_c2_trust_assessment() -> None:
    from app.schemas.ai import TrustAssessment

    result = scorer.assess(TrustInputs(real_count=1, has_real_details=True, vague_or_joking=False), "high")
    assert TrustAssessment.model_validate(result.model_dump()) == result
