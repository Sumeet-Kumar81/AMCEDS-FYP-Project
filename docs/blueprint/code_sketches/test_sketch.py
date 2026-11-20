import json
import pytest
from pydantic import ValidationError
from coordination import Candidate, DupSettings, best_candidates, score_candidate
from pipeline import Job, run_pipeline
from policy import decide_action
from allocation import Needed, Vehicle, rank, vehicles_needed
from schemas_ai import TriageResult
from trust import TrustInputs, score_report
from triage import TriageFailed, run_triage, script_hint


# ---------- TrustScorer (SRS Table 7.3.1) ----------
def test_trust_neutral_start_is_50_medium():
    t = score_report(TrustInputs())
    assert (t.score, t.tier, t.signals) == (50, "medium", [])

def test_trust_two_fakes_gives_low_tc09():
    t = score_report(TrustInputs(fake_count=2))
    assert t.score == 0 and t.tier == "low"            # 50 - 60 = -10, clamped to 0

def test_trust_fake_penalty_stops_at_minus_60():
    t = score_report(TrustInputs(fake_count=5))
    assert [s.points for s in t.signals] == [-60]

def test_trust_gps_far_is_minus_20_tc11():
    assert score_report(TrustInputs(distance_to_gps_m=100)).score == 65     # +15
    assert score_report(TrustInputs(distance_to_gps_m=2500)).score == 30    # -20

def test_trust_gps_between_500m_and_2km_no_signal():
    assert score_report(TrustInputs(distance_to_gps_m=1000)).score == 50

def test_trust_tier_boundaries():
    # +15 real history +10 details = 75 high ; 50+15=65 medium; 50-15(vague)=35 low; 40 boundary
    assert score_report(TrustInputs(real_count=1, has_real_details=True)).tier == "high"
    assert score_report(TrustInputs(real_count=1)).tier == "medium"
    assert score_report(TrustInputs(vague_or_joking=True)).tier == "low"
    assert score_report(TrustInputs(vague_or_joking=True, has_real_details=True)).score == 45

def test_trust_nearby_one_vs_many():
    assert score_report(TrustInputs(independent_nearby=1)).score == 65
    assert score_report(TrustInputs(independent_nearby=4)).score == 75

def test_trust_clamped_0_100():
    t = score_report(TrustInputs(real_count=1, distance_to_gps_m=10, independent_nearby=3, has_real_details=True))
    assert t.score == 100 and t.tier == "high"
    assert score_report(TrustInputs(fake_count=9, device_flood=True, vague_or_joking=True)).score == 0

def test_trust_every_signal_has_a_reason():
    t = score_report(TrustInputs(real_count=1, has_real_details=True))
    assert {s.code for s in t.signals} == {"real_history", "details"} and all(s.detail for s in t.signals)


# ---------- Policy (Table 7.3.2) ----------
@pytest.mark.parametrize("tier,sev,expected", [
    ("high", "low", "continue"), ("high", "critical", "continue"),
    ("medium", "low", "continue_and_confirm"), ("medium", "critical", "continue_and_confirm"),
    ("low", "low", "review_queue"), ("low", "medium", "review_queue"),
    ("low", "high", "urgent_with_warning"), ("low", "critical", "urgent_with_warning"),
])
def test_policy_truth_table(tier, sev, expected):
    assert decide_action(tier, sev) == expected

def test_policy_urgent_is_never_held_back():                # NFR-S3
    for tier in ("high", "medium", "low"):
        for sev in ("high", "critical"):
            assert decide_action(tier, sev) != "review_queue"


# ---------- Coordination (Table 7.3.4) ----------
def test_duplicate_tc13_close_and_recent_with_same_text_auto_links():
    r = score_candidate(Candidate(1, True, 100, 5 * 60, 0.9))
    assert r.decision == "auto_link" and r.confidence >= 85

def test_finding_linear_decay_can_never_auto_link_tc13():
    # D-007 as first written (linear). At 100 m / 5 min even a perfect text match tops out at 80 < 85.
    lin = DupSettings(decay=1.0)
    r = score_candidate(Candidate(1, True, 100, 5 * 60, 1.0), lin)
    assert r.confidence == 80.0 and r.decision == "possible"

def test_duplicate_tc14_two_km_not_compared():
    assert score_candidate(Candidate(1, True, 2000, 60, 1.0)).decision == "not_compared"

def test_duplicate_different_type_never_compared():
    assert score_candidate(Candidate(1, False, 10, 10, 1.0)).decision == "not_compared"

def test_duplicate_older_than_15_min_not_compared():
    assert score_candidate(Candidate(1, True, 10, 16 * 60, 1.0)).decision == "not_compared"

def test_duplicate_medium_band_asks_dispatcher():
    r = score_candidate(Candidate(1, True, 150, 7 * 60, 0.6))
    assert r.decision == "possible" and 60 <= r.confidence < 85

def test_duplicate_low_confidence_stays_separate():
    r = score_candidate(Candidate(1, True, 280, 14 * 60, 0.1))
    assert r.decision == "separate" and r.confidence < 60

def test_only_one_auto_link_wins():
    out = best_candidates([Candidate(1, True, 10, 10, 1.0), Candidate(2, True, 20, 20, 1.0)])
    assert [r.decision for r in out] == ["auto_link", "possible"]


# ---------- Resource allocation (Table 7.3.3) ----------
def ambs(n): return [Vehicle(i, "ambulance", 100 + i * 10, 1000 + i) for i in range(1, n + 1)]

def test_tc16_six_victims_three_ambulances_and_two_spare():
    need = vehicles_needed("accident", "high", 6)
    assert need.counts == {"ambulance": 3}
    a = rank(ambs(8), need)
    assert len(a.chosen) == 3 and len(a.spare) == 2 and a.shortage == {}

def test_tc17_unknown_victims_one_vehicle_and_check_flag():
    need = vehicles_needed("accident", "medium", None)
    assert need.counts == {"ambulance": 1} and need.victims_unknown

def test_tc18_fire_has_truck_ambulance_and_backup():
    assert vehicles_needed("fire", "high", 2).counts == {"fire_truck": 1, "ambulance": 1, "backup": 1}

def test_critical_accident_adds_backup():
    assert vehicles_needed("accident", "critical", 2).counts == {"ambulance": 1, "backup": 1}

def test_tc19_shortage_reports_how_many_free():
    a = rank(ambs(2), vehicles_needed("accident", "high", 6))
    assert a.shortage == {"ambulance": 2} and len(a.chosen) == 2

def test_other_type_leaves_choice_to_dispatcher():
    assert vehicles_needed("other", "low", 1).dispatcher_chooses

def test_ranking_is_by_eta_with_stable_tie_break():
    v = [Vehicle(9, "ambulance", 100, 5), Vehicle(2, "ambulance", 100, 5), Vehicle(5, "ambulance", 50, 9)]
    a = rank(v, Needed({"ambulance": 2}), spare_count=1)
    assert [x.vehicle_id for x in a.chosen] == [5, 2] and [x.vehicle_id for x in a.spare] == [9]


# ---------- Triage with a fake LLM ----------
class FakeLLM:
    def __init__(self, *replies): self.replies, self.calls = list(replies), 0
    def complete_json(self, system, user):
        self.calls += 1
        return self.replies.pop(0)

GOOD = json.dumps({"language": "en", "incident_type": "accident", "severity": "high", "victims_estimate": 4,
                   "location_words": "near the market", "has_real_details": True, "vague_or_joking": False,
                   "overall_confidence": 0.9})

def test_triage_tc06_accident_high_victims():
    r = run_triage("Bus accident near the market, many people hurt", FakeLLM(GOOD))
    assert (r.incident_type, r.severity, r.victims_estimate, r.review_reasons) == ("accident", "high", 4, [])

def test_triage_tc07_no_location_marks_missing_info():
    bad = json.loads(GOOD); bad["location_words"] = None
    r = run_triage("help", FakeLLM(json.dumps(bad)))
    assert "missing_info" in r.review_reasons

def test_triage_gps_present_means_location_is_not_missing():
    bad = json.loads(GOOD); bad["location_words"] = None
    assert "missing_info" not in run_triage("help", FakeLLM(json.dumps(bad)), has_gps=True).review_reasons

def test_triage_tc08_low_confidence_flag():
    low = json.loads(GOOD); low["overall_confidence"] = 0.55
    assert "low_confidence" in run_triage("something", FakeLLM(json.dumps(low))).review_reasons

def test_triage_invalid_json_then_valid_retries_once():
    llm = FakeLLM("not json", GOOD)
    assert run_triage("x", llm).incident_type == "accident" and llm.calls == 2

def test_triage_invalid_twice_raises():
    with pytest.raises(TriageFailed):
        run_triage("x", FakeLLM("nope", "still nope"))

def test_triage_rejects_made_up_fields_and_out_of_range():
    bad = json.loads(GOOD); bad["dispatch_vehicle"] = 7
    with pytest.raises(TriageFailed):
        run_triage("x", FakeLLM(json.dumps(bad), json.dumps(bad)))
    with pytest.raises(ValidationError):
        TriageResult(language="en", overall_confidence=1.4)

def test_script_hint_detects_urdu_script():
    assert script_hint("سڑک پر حادثہ ہوا ہے") == "ur-script" and script_hint("accident here") == "latin"


# ---------- Pipeline order and safety ----------
class FakeStore:
    def __init__(self): self.log = []
    def save_triage(self, i, r): self.log.append("save_triage")
    def save_trust(self, i, t, a): self.log.append(f"save_trust:{a}")
    def save_duplicates(self, i, r): self.log.append(f"save_duplicates:{len(r)}")
    def save_allocation(self, i, a): self.log.append(f"save_allocation:{len(a.chosen)}")
    def mark_stage_failed(self, i, s, e): self.log.append(f"failed:{s}")
    def mark_done(self, i): self.log.append("done")

def job(**kw): return Job(incident_id=1, text="t", available_vehicles=lambda: ambs(6), **kw)

def test_pipeline_happy_path_runs_all_stages_in_order():
    s = FakeStore()
    assert run_pipeline(job(), s, FakeLLM(GOOD)) == ["triage", "trust", "coordination", "allocation"]
    assert s.log[0] == "save_triage" and s.log[-1] == "done"

def test_pipeline_triage_failure_is_recorded_and_nothing_else_runs():   # TC-44 spirit
    s = FakeStore()
    assert run_pipeline(job(), s, FakeLLM("x", "y")) == []
    assert s.log == ["failed:triage"]

def test_pipeline_low_trust_low_severity_skips_allocation():
    low = json.loads(GOOD); low["severity"] = "low"
    s = FakeStore()
    ran = run_pipeline(job(trust_inputs=TrustInputs(fake_count=2)), s, FakeLLM(json.dumps(low)))
    assert ran == ["triage", "trust", "coordination"] and "save_trust:review_queue" in s.log   # duplicates still checked

def test_pipeline_low_trust_critical_still_allocates_nfr_s3():
    crit = json.loads(GOOD); crit["severity"] = "critical"
    s = FakeStore()
    ran = run_pipeline(job(trust_inputs=TrustInputs(fake_count=2)), s, FakeLLM(json.dumps(crit)))
    assert ran == ["triage", "trust", "coordination", "allocation"] and "save_trust:urgent_with_warning" in s.log

def test_pipeline_saves_a_possible_duplicate_for_dispatcher_and_still_allocates():
    from coordination import Candidate
    s = FakeStore()
    j = Job(incident_id=1, text="t", available_vehicles=lambda: ambs(6),
            duplicate_candidates=lambda: [Candidate(7, True, 150, 7 * 60, 0.6)])
    ran = run_pipeline(j, s, FakeLLM(GOOD))
    assert "save_duplicates:1" in s.log and "allocation" in ran      # possible duplicate never blocks dispatch (NFR-S3/S4)
