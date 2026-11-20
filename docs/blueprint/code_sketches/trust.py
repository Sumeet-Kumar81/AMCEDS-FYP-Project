"""Rule-based TrustScorer: SRS Table 7.3.1. No LLM. Real file: backend/app/agents/trust.py"""
from __future__ import annotations
from dataclasses import dataclass
from schemas_ai import TrustAssessment, TrustSignal


@dataclass(frozen=True)
class TrustInputs:
    real_count: int = 0                    # earlier reports of this caller/device confirmed real
    fake_count: int = 0                    # earlier reports marked fake
    distance_to_gps_m: float | None = None # caller GPS vs place named in the text; None = unknown
    independent_nearby: int = 0            # other independent reports nearby (UC-04 rules)
    has_real_details: bool = False
    vague_or_joking: bool = False
    device_flood: bool = False


@dataclass(frozen=True)
class TrustSettings:                       # defaults = SRS Appendix C; admin can change them
    start: int = 50
    real_history: int = 15
    fake_each: int = 30
    fake_floor: int = 60
    gps_near_m: int = 500
    gps_near_pts: int = 15
    gps_far_m: int = 2000
    gps_far_pts: int = -20
    nearby_one: int = 15
    nearby_two_plus: int = 25
    details: int = 10
    vague: int = -15
    flood: int = -20
    high_min: int = 70
    medium_min: int = 40


def score_report(i: TrustInputs, s: TrustSettings = TrustSettings()) -> TrustAssessment:
    signals: list[TrustSignal] = []

    def add(code: str, pts: int, detail: str) -> None:
        signals.append(TrustSignal(code=code, points=pts, detail=detail))

    if i.real_count > 0:
        add("real_history", s.real_history, f"{i.real_count} earlier report(s) confirmed real")
    if i.fake_count > 0:
        pts = -min(s.fake_each * i.fake_count, s.fake_floor)
        add("fake_history", pts, f"{i.fake_count} earlier report(s) marked fake")
    if i.distance_to_gps_m is not None:
        if i.distance_to_gps_m <= s.gps_near_m:
            add("gps_match", s.gps_near_pts, f"GPS {i.distance_to_gps_m:.0f} m from named place")
        elif i.distance_to_gps_m > s.gps_far_m:
            add("gps_far", s.gps_far_pts, f"GPS {i.distance_to_gps_m:.0f} m from named place")
    if i.independent_nearby == 1:
        add("nearby_1", s.nearby_one, "one other independent report nearby")
    elif i.independent_nearby >= 2:
        add("nearby_2plus", s.nearby_two_plus, f"{i.independent_nearby} other independent reports nearby")
    if i.has_real_details:
        add("details", s.details, "message has place, event or people hurt")
    if i.vague_or_joking:
        add("vague", s.vague, "message is vague or joking")
    if i.device_flood:
        add("flood", s.flood, "device sent many reports in a short time")

    score = max(0, min(100, s.start + sum(x.points for x in signals)))
    tier = "high" if score >= s.high_min else "medium" if score >= s.medium_min else "low"
    return TrustAssessment(score=score, tier=tier, signals=signals)
