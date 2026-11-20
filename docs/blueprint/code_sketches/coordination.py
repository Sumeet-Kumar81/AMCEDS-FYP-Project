"""Duplicate scoring (D-007 weights are PROPOSED, not approved). Real file: backend/app/agents/coordination.py"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

Decision = Literal["auto_link", "possible", "separate", "not_compared"]


@dataclass(frozen=True)
class DupSettings:
    distance_m: float = 300      # SRS Table 7.3.4
    window_min: float = 15
    auto_link: float = 85
    possible: float = 60
    w_dist: float = 0.40         # D-007 proposal
    w_time: float = 0.20
    w_meaning: float = 0.40
    decay: float = 2.0           # 1.0 = linear (D-007 as first written); 2.0 = quadratic (see blueprint finding)


@dataclass(frozen=True)
class Candidate:
    incident_id: int
    same_type: bool
    distance_m: float
    time_diff_s: float
    meaning: float               # 0..1 text similarity


@dataclass(frozen=True)
class DupResult:
    incident_id: int
    confidence: float
    decision: Decision


def score_candidate(c: Candidate, s: DupSettings = DupSettings()) -> DupResult:
    # Gates first: wrong type, too far or too old are never compared (TC-14).
    if (not c.same_type) or c.distance_m > s.distance_m or c.time_diff_s > s.window_min * 60:
        return DupResult(c.incident_id, 0.0, "not_compared")
    s_dist = 1 - (c.distance_m / s.distance_m) ** s.decay
    s_time = 1 - (c.time_diff_s / (s.window_min * 60)) ** s.decay
    conf = 100 * (s.w_dist * s_dist + s.w_time * s_time + s.w_meaning * max(0.0, min(1.0, c.meaning)))
    conf = round(conf, 1)
    if conf >= s.auto_link:
        return DupResult(c.incident_id, conf, "auto_link")
    if conf >= s.possible:
        return DupResult(c.incident_id, conf, "possible")   # dispatcher must confirm (NFR-S4)
    return DupResult(c.incident_id, conf, "separate")


def best_candidates(cands: list[Candidate], s: DupSettings = DupSettings()) -> list[DupResult]:
    results = [score_candidate(c, s) for c in cands]
    results = [r for r in results if r.decision != "not_compared"]
    results.sort(key=lambda r: (-r.confidence, r.incident_id))
    # Only the single best auto-link may link; any other would-be auto-link is demoted to "possible".
    seen_auto = False
    out: list[DupResult] = []
    for r in results:
        if r.decision == "auto_link":
            if seen_auto:
                r = DupResult(r.incident_id, r.confidence, "possible")
            seen_auto = True
        out.append(r)
    return out
