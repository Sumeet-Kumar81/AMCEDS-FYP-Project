"""Trust Scorer (SRS UC-03, Appendix C Table 7.3.1; D-012). Task B1-A2-06.

A deterministic, rule-based part of the Triage step: it is **not** an agent and uses **no** language
model. Every point it gives or takes comes with a reason (SDS Table 6.3), so the dispatcher can see
why a report got its tier.

* All points and limits come from the incident's own settings snapshot (new settings apply to new
  incidents only, UC-12); missing keys fall back to the SRS defaults.
* No caller history counts as neutral (UC-03 1a): no points either way.
* Low AI confidence is **not** an input: it can never lower trust or make a report fake (D-012).
* D-035 (approved 2026-11-21): if the Triage AI failed, the two AI-based signals ("real details",
  "vague or joking") are skipped and an ``ai_unavailable`` note (0 points) is added; the tier comes
  from the remaining signals.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.agents.policy import decide_action
from app.schemas.ai import TrustAssessment, TrustSignal
from app.schemas.enums import Severity, TrustTier
from app.services.settings import REGISTRY


@dataclass(frozen=True)
class TrustInputs:
    real_count: int = 0  # earlier reports of this caller/device confirmed real
    fake_count: int = 0  # earlier reports marked fake
    distance_to_gps_m: float | None = None  # caller GPS vs the place in the message; None = not known
    independent_nearby: int = 0  # other independent reports nearby (distinct callers, D-012)
    has_real_details: bool | None = None  # from Triage; None = Triage unavailable (D-035)
    vague_or_joking: bool | None = None  # from Triage; None = Triage unavailable (D-035)
    device_flood: bool = False  # the device or number sent too many reports (callers.flagged_until)


@dataclass(frozen=True)
class TrustSettings:
    start: int
    real_history: int
    fake_each: int  # negative
    fake_floor: int  # negative: the most the fake history can take away
    gps_match_m: int
    gps_match: int
    gps_far_m: int
    gps_far: int
    one_nearby: int
    two_nearby: int
    real_details: int
    vague: int
    flood: int
    tier_high: int
    tier_medium: int

    @classmethod
    def from_settings(cls, values: Mapping[str, int | float]) -> TrustSettings:
        def get(key: str) -> int:
            return int(values.get(key, REGISTRY[key].default))

        return cls(
            start=get("trust_start"), real_history=get("trust_pts_real_history"),
            fake_each=get("trust_pts_fake_each"), fake_floor=get("trust_pts_fake_floor"),
            gps_match_m=get("trust_gps_match_m"), gps_match=get("trust_pts_gps_match"),
            gps_far_m=get("trust_gps_far_m"), gps_far=get("trust_pts_gps_far"),
            one_nearby=get("trust_pts_one_nearby"), two_nearby=get("trust_pts_two_nearby"),
            real_details=get("trust_pts_real_details"), vague=get("trust_pts_vague"), flood=get("trust_pts_flood"),
            tier_high=get("trust_tier_high"), tier_medium=get("trust_tier_medium"),
        )


DEFAULT_SETTINGS = TrustSettings.from_settings({})


def tier_for(score: int, s: TrustSettings = DEFAULT_SETTINGS) -> TrustTier:
    if score >= s.tier_high:
        return TrustTier.HIGH
    return TrustTier.MEDIUM if score >= s.tier_medium else TrustTier.LOW


def signals_for(i: TrustInputs, s: TrustSettings = DEFAULT_SETTINGS) -> list[TrustSignal]:
    out: list[TrustSignal] = []

    def add(code: str, points: int, detail: str) -> None:
        out.append(TrustSignal(code=code, points=points, detail=detail))

    if i.real_count > 0:
        add("real_history", s.real_history, f"{i.real_count} earlier report(s) from this caller confirmed real")
    if i.fake_count > 0:
        add("fake_history", max(s.fake_floor, s.fake_each * i.fake_count),
            f"{i.fake_count} earlier report(s) from this caller marked fake")
    if i.distance_to_gps_m is not None:
        if i.distance_to_gps_m <= s.gps_match_m:
            add("gps_match", s.gps_match, f"caller GPS {i.distance_to_gps_m:.0f} m from the place in the message")
        elif i.distance_to_gps_m > s.gps_far_m:
            add("gps_far", s.gps_far, f"caller GPS {i.distance_to_gps_m:.0f} m from the place in the message")
    if i.independent_nearby == 1:
        add("nearby_one", s.one_nearby, "one other independent report nearby")
    elif i.independent_nearby >= 2:
        add("nearby_two_plus", s.two_nearby, f"{i.independent_nearby} other independent reports nearby")
    if i.has_real_details is None and i.vague_or_joking is None:
        add("ai_unavailable", 0, "Triage AI unavailable: message details not scored (D-035)")
    else:
        if i.has_real_details:
            add("real_details", s.real_details, "the message names a place, an event or people hurt")
        if i.vague_or_joking:
            add("vague", s.vague, "the message is vague or joking")
    if i.device_flood:
        add("flood", s.flood, "the device or number sent many reports in a short time")
    return out


class TrustScorer:
    """Score a report and decide the next step (Table 7.3.1, then Table 7.3.2)."""

    def assess(self, inputs: TrustInputs, severity: Severity | str | None,
               settings: Mapping[str, int | float] | None = None) -> TrustAssessment:
        s = TrustSettings.from_settings(settings or {})
        signals = signals_for(inputs, s)
        score = max(0, min(100, s.start + sum(x.points for x in signals)))
        tier = tier_for(score, s)
        return TrustAssessment(score=score, tier=tier, signals=signals, action=decide_action(tier, severity))
