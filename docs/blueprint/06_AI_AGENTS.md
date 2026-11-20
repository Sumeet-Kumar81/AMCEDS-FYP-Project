# Part 6 — Multi-agent AI implementation

**Status of the code in this file:** the Python blocks are copied from `code_sketches/` and are **tested** (46 pytest tests pass, command and result in `10_TESTING.md` §10.9). They are *design sketches*, not application code: they use flat module names, an in-memory fake store and a fake LLM. Real files go to the paths named in each section. The **LangGraph wiring in §6.7 is NOT verified** because LangGraph is not installed in the authoring environment. Constants marked *proposed* belong to open decisions (D-007, D-019, D-021, D-033, D-035) and are not approved requirements.

## 6.1 Principles

1. **Three agents, three jobs.** Triage, Coordination, Resource Allocation. The Trust Scorer is a rule-based module inside the Triage step (D-012). No fourth agent.
2. **LLM only where language is the problem.** Only the Triage Agent calls a language model. Everything else is deterministic code with fixed rules from SRS Appendix C.
3. **Output is data, not authority.** Every model output is validated against a Pydantic schema (`extra="forbid"`). Invalid output is retried once, then the stage fails safely. Model text never sets a status, a vehicle or a dispatch.
4. **Agents recommend.** They have no write access to `vehicles`, `assignments` or `status = dispatched`. Their only door to the database is `pipeline_store` (contract C-6).
5. **Unknown stays unknown.** `null` for what the report did not say. Locations are never guessed.
6. **Every stage saves before the next starts**, so a later failure cannot erase earlier results and the original report is never touched.

## 6.2 Shared schemas (contract C-2) — `backend/app/schemas/ai.py`

```python
"""Illustrative C-2 schemas (blueprint sketch). Real file: backend/app/schemas/ai.py"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

IncidentType = Literal["accident", "fire", "medical", "other"]
Severity = Literal["low", "medium", "high", "critical"]
Tier = Literal["high", "medium", "low"]
Action = Literal["continue", "continue_and_confirm", "review_queue", "urgent_with_warning"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TriageResult(Strict):
    language: str
    incident_type: IncidentType | None = None      # None = the report did not say
    severity: Severity | None = None
    victims_estimate: int | None = Field(default=None, ge=0, le=500)
    location_words: str | None = None              # never guessed
    has_real_details: bool = False
    vague_or_joking: bool = False
    overall_confidence: float = Field(ge=0.0, le=1.0)   # stored 0..1, shown as 0..100 %
    transcript_unclear: bool = False
    review_reasons: list[str] = Field(default_factory=list)


class TrustSignal(Strict):
    code: str
    points: int
    detail: str


class TrustAssessment(Strict):
    score: int = Field(ge=0, le=100)
    tier: Tier
    signals: list[TrustSignal]
```

The real C-2 adds per-field confidences (`type_confidence`, `severity_confidence`, `victims_confidence`), `language_confidence`, `model`, `prompt_version`, `latency_ms`, and the schemas for geocoding, duplicates and allocation listed in B1-A2-01.

## 6.3 Agent 1 — Triage Agent

| Item | Design |
|---|---|
| **Responsibility** | Language, incident type, location words, victims, severity, confidence; flags `has_real_details`, `vague_or_joking`, `transcript_unclear` |
| **Input** | `TriageInput`: text (typed, SMS, or transcript), channel, optional caller GPS, optional typed location text. Voice reports first pass through speech-to-text in the worker |
| **Output** | `TriageResult` saved by `save_triage` into `incidents` columns + `ai_details` (JSONB) |
| **Steps** | (1) speech-to-text if voice (faster-whisper, `transcript_unclear` from log-probability) → (2) script check (Arabic vs Latin) gives a language hint → (3) **one LLM call** through the Gateway with JSON-only prompt → (4) Pydantic validation, one retry with the error appended → (5) deterministic post-rules add review reasons → (6) save |
| **Rule-based part** | `confidence < 0.60` → `low_confidence`; no type, or no location words **and** no GPS → `missing_info` (SRS UC-02) |
| **Libraries** | `faster-whisper`, `httpx` (Gateway providers), `pydantic`, `langgraph` (node wrapper) |
| **DB interaction** | Only `pipeline_store.save_triage`, `save_location`, `save_transcript`, `mark_stage_failed` |
| **Errors** | Timeout/connection → retry ≤ 2 with backoff; invalid JSON twice → `TriageFailed` → incident `needs_check` + `ai_failed` + WebSocket `incident.ai_failed`; dispatcher works manually (UC-02 alternates, NFR-S5) |
| **Testing** | Fake LLM unit tests for TC-06/07/08, invalid-JSON retry, schema rejection of made-up fields; later labelled-set accuracy (NFR-P7/P8) |

### Prompt design

- One system prompt, versioned file `agents/prompts/triage_v1.md`; `prompt_version` stored with every result.
- Contents: role (read one report), allowed JSON keys and enums, "use null when not stated", "never guess a location", 4–6 short **simulated** few-shot examples in English, Urdu script, Roman-Urdu and mixed language. No real data in prompts.
- Temperature 0, JSON mode where the provider supports it, 8 s timeout (protects NFR-P1).
- The model is told the **report text only**; it never sees caller history, trust data or vehicle availability (keeps trust independent of the LLM and prevents prompt-based manipulation of dispatch).

### Confidence (proposed, to be calibrated in Batch 8)

1. The model returns a confidence per field (type, severity, victims, location).
2. `overall_confidence = min(type_conf, severity_conf)`, then deterministic caps: × 0.8 if `transcript_unclear`; ≤ 0.59 if type is `null`.
3. Stored 0–1, shown as 0–100 % next to every AI value (NFR-S2).
4. In B8 build a **reliability table** (predicted bucket vs measured accuracy on the labelled set). If the model over-claims, rescale. Low confidence only asks the dispatcher to check; it **never** lowers trust and never marks a report fake (D-012).

### Triage sketch — `backend/app/agents/triage.py`

```python
"""Triage Agent sketch: LLM output is only accepted if it passes the schema. Real file: backend/app/agents/triage.py"""
from __future__ import annotations
import json
from typing import Protocol
from pydantic import ValidationError
from schemas_ai import TriageResult

MIN_CONFIDENCE = 0.60            # SRS: below 60 % the dispatcher must check


class LLMClient(Protocol):                       # the replaceable LLM Gateway interface
    def complete_json(self, system: str, user: str) -> str: ...


class TriageFailed(Exception):
    """The model output could not be validated twice. Orchestrator marks the incident needs_check."""


SYSTEM = (
    "You read one emergency report (English, Urdu, Sindhi or mixed). Return ONLY a JSON object with keys: "
    "language, incident_type (accident|fire|medical|other|null), severity (low|medium|high|critical|null), "
    "victims_estimate (int|null), location_words (string|null), has_real_details, vague_or_joking, "
    "overall_confidence (0..1). Use null when the report does not say. Never guess a location."
)


def script_hint(text: str) -> str:
    arabic = sum(1 for ch in text if "؀" <= ch <= "ۿ")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "ur-script" if arabic > latin else "latin"


def run_triage(text: str, llm: LLMClient, has_gps: bool = False) -> TriageResult:
    user = f"Report:\n{text}"
    last_error = ""
    for attempt in range(2):                                  # one retry with the error shown to the model
        raw = llm.complete_json(SYSTEM, user + (f"\nFix this error: {last_error}" if last_error else ""))
        try:
            result = TriageResult.model_validate(json.loads(raw))
            break
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:300]
    else:
        raise TriageFailed(last_error)

    reasons = list(result.review_reasons)                     # deterministic post-rules, not the LLM's call
    if result.overall_confidence < MIN_CONFIDENCE:
        reasons.append("low_confidence")
    if result.incident_type is None or (result.location_words is None and not has_gps):
        reasons.append("missing_info")
    return result.model_copy(update={"review_reasons": sorted(set(reasons))})
```

## 6.4 The Trust Scorer (not an agent) and the action policy

| Item | Design |
|---|---|
| **Responsibility** | Estimate how likely a report is real using SRS Table 7.3.1; produce score, tier and a reason for every point |
| **Why not an LLM** | Fixed, auditable, explainable rules; a model could be talked into trusting a fake |
| **Inputs** | Caller history (`real_count`, `fake_count`), GPS-to-text distance (from geocoding), count of independent nearby reports (`count_independent_nearby` in C-6: distinct callers/devices, same type, within the duplicate distance/window), the two triage flags, the device-flood flag |
| **Output** | `TrustAssessment {score, tier, signals[]}` saved in `trust_score`, `trust_tier`, `trust_signals` |
| **Doubtful vs fake** | Doubtful = low tier or review reasons → review queue (UC-07). **Fake** is set only by a dispatcher decision (TC-24); `fake_count` then affects future reports |
| **Settings** | Weights and tier limits come from the settings snapshot, so admin changes affect new incidents only |
| **Testing** | One test per signal, floor at −60, clamp 0–100, tier boundaries, TC-09, TC-11; the action policy has a full truth table and a property test: severity high/critical never yields `review_queue` |

### Scorer and policy sketch — `agents/trust.py`, `agents/policy.py`

```python
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
```

```python
"""SRS Table 7.3.2 as a pure function. Real file: backend/app/agents/policy.py"""
from schemas_ai import Action, Severity, Tier

URGENT = {"high", "critical"}


def decide_action(tier: Tier, severity: Severity) -> Action:
    if tier == "high":
        return "continue"
    if tier == "medium":
        return "continue_and_confirm"          # confirmation runs at the same time, never blocks
    # low tier
    return "urgent_with_warning" if severity in URGENT else "review_queue"
```

> **Open point U-8 / D-035:** if Triage fails, "real details" and "vague" are unknown, but NFR-S2 still wants a tier on every report. Proposal: run the scorer on its non-LLM signals (history, GPS, nearby, flood) in the failure path and label it "AI unavailable". Not in the sketch until approved.

## 6.5 Agent 2 — Coordination Agent

| Item | Design |
|---|---|
| **Responsibility** | Decide whether a triaged report belongs to an already open incident |
| **Input** | The new incident + candidate rows from `find_duplicate_candidates`: **same type**, open, not fake, within 300 m (`ST_DWithin` on `geography`), within 15 min, excluding itself |
| **Output** | `DuplicateCandidateResult[]` with distance, time gap, per-signal scores, match confidence and decision `auto_link` / `possible` / `separate` |
| **Steps** | (1) SQL narrows candidates with the gates (PostGIS does the geography) → (2) score each candidate → (3) only the single best candidate may auto-link → (4) save results; auto-link sets `group_id` on both incidents **without changing either incident's status** and is reversible → (5) `possible` rows wait for the dispatcher (`duplicate.candidate` event) |
| **Safety** | No answer from the dispatcher = reports stay separate and each stays dispatchable (TC-15, D-020). A link never hides or closes anything (NFR-S4) |
| **Libraries** | none required for scoring; text similarity per D-007 (sentence-transformers or character n-gram TF-IDF) |
| **DB interaction** | `find_duplicate_candidates`, `save_duplicate_results` |
| **Testing** | TC-13, TC-14, TC-15, boundary 84.9/85.0, different type never compared, only one auto-link |

### Candidate query (reference, `db/sql/duplicate_candidates.sql`)

```sql
SELECT c.incident_id,
       ST_Distance(c.location::geography, :pt::geography)        AS distance_m,
       EXTRACT(EPOCH FROM (:received_at - c.received_at))        AS time_diff_s,
       c.original_text
FROM incidents c
WHERE c.incident_id <> :id
  AND c.incident_type = :type
  AND c.status NOT IN ('closed', 'fake')
  AND c.received_at BETWEEN :received_at - make_interval(mins => :window_min) AND :received_at
  AND ST_DWithin(c.location::geography, :pt::geography, :distance_m);
```

### Scoring sketch — `agents/coordination.py`

```python
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
```

> **Finding (U-1 → D-033):** D-007 as first written used *linear* decay. The sketch's test `test_finding_linear_decay_can_never_auto_link_tc13` shows that with linear decay a report 100 m and 5 min away with a perfect text match scores only 80 — below the 85 needed — so TC-13 could never pass. The sketch uses quadratic decay (`decay = 2.0`); the same case scores about 93. The exact curve and weights must be tuned on `duplicate_groups.jsonl` against NFR-P9 (≥ 80 % found, ≤ 5 % wrong merges) and approved.

## 6.6 Agent 3 — Resource Allocation Agent

| Item | Design |
|---|---|
| **Responsibility** | Choose vehicle types and counts, rank free vehicles by travel time, show needed + 2 spare, warn about shortage |
| **Input** | Triaged incident (type, severity, victims, location) + available vehicles (`list_available_vehicles`: status available, no open assignment, driver on duty, recent GPS) + settings (`patients_per_ambulance` default 2, `spare_vehicles` default 2) |
| **Output** | `AllocationResult` → `recommendations` rows (new `batch_no`, old batch kept) and `allocation_summary` |
| **Rules (Table 7.3.3)** | Accident: ambulances = ⌈victims ÷ 2⌉, min 1; critical → + 1 backup. Fire: ≥ 1 fire truck + ambulances by the same rule + backup. Medical: ambulances, min 1. Other: dispatcher chooses. Victims unknown: 1 vehicle (per type — U-3) and a "dispatcher must check" flag |
| **Ranking** | OSRM **`table`** call (many vehicles in one request) → ETA; sort by ETA, then distance, then id (deterministic). OSRM down → haversine × road factor ÷ fallback speed, `eta_is_approximate = true`, `routing_mode = straight_line` |
| **Never** | lock, assign or update a vehicle (NFR-S6, UC-05 post-condition). Tested with a read-only fake store |
| **Hospital suggestion** | Separate helper (`agents/hospital.py`, D-018): nearest active hospital by ETA whose departments match; dispatcher can change |
| **Re-runs** | Job `reallocate` after dispatcher edit, driver decline, or Real decision; recommendations of the previous batch become `is_current = false` |
| **Testing** | TC-16 (6 victims → 3 ambulances + 2 spare), TC-17, TC-18, TC-19, TC-20; locked vehicles never appear |

### Allocation sketch — `agents/resource.py`

```python
"""Vehicle counts (SRS Table 7.3.3) and ETA ranking. D-019 points are PROPOSED. Real file: backend/app/agents/resource.py (named allocation here only because "resource" is a Python standard-library name)"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Needed:
    counts: dict[str, int]                 # e.g. {"ambulance": 3}
    victims_unknown: bool = False          # dispatcher must check (TC-17)
    dispatcher_chooses: bool = False       # incident type "other"


def vehicles_needed(incident_type: str, severity: str, victims: int | None,
                    patients_per_ambulance: int = 2) -> Needed:
    unknown = victims is None
    amb = 1 if unknown else max(1, math.ceil(victims / patients_per_ambulance))
    if incident_type == "accident":
        c = {"ambulance": amb}
        if severity == "critical":
            c["backup"] = 1
        return Needed(c, victims_unknown=unknown)
    if incident_type == "fire":
        return Needed({"fire_truck": 1, "ambulance": amb, "backup": 1}, victims_unknown=unknown)
    if incident_type == "medical":
        return Needed({"ambulance": amb}, victims_unknown=unknown)
    return Needed({}, dispatcher_chooses=True)


@dataclass(frozen=True)
class Vehicle:
    vehicle_id: int
    vehicle_type: str
    eta_s: float
    distance_m: float
    eta_approximate: bool = False


@dataclass
class Allocation:
    chosen: list[Vehicle] = field(default_factory=list)
    spare: list[Vehicle] = field(default_factory=list)
    shortage: dict[str, int] = field(default_factory=dict)    # type -> how many are free
    victims_unknown: bool = False


def rank(available: list[Vehicle], need: Needed, spare_count: int = 2) -> Allocation:
    """`available` must already exclude vehicles that are locked or not on duty.
    Nothing here writes to the database: recommending never locks a vehicle (NFR-S6)."""
    key = lambda v: (v.eta_s, v.distance_m, v.vehicle_id)         # deterministic tie-break
    out = Allocation(victims_unknown=need.victims_unknown)
    used: set[int] = set()
    for vtype, n in need.counts.items():
        pool = sorted((v for v in available if v.vehicle_type == vtype), key=key)
        out.chosen += pool[:n]
        used.update(v.vehicle_id for v in pool[:n])
        if len(pool) < n:
            out.shortage[vtype] = len(pool)
    rest = sorted((v for v in available if v.vehicle_id not in used and v.vehicle_type in need.counts), key=key)
    out.spare = rest[:spare_count]
    return out
```

## 6.7 Orchestration

`agents/orchestrator.py` builds the stage order below. The **logic** (which stage runs when, what is saved, how failure is handled) is the tested sketch; LangGraph supplies typed state, conditional edges and retries around the same functions.

### Tested stage logic — `pipeline.py`

```python
"""Stage order of the AI worker (what the LangGraph graph wires up). Real file: backend/app/agents/orchestrator.py"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Callable, Protocol
from coordination import Candidate, best_candidates
from policy import decide_action
from allocation import Needed, Vehicle, rank, vehicles_needed
from trust import TrustInputs, score_report
from triage import LLMClient, TriageFailed, run_triage

URGENT = {"high", "critical"}


class Store(Protocol):                           # contract C-6 (pipeline_store), reduced for the sketch
    def save_triage(self, incident_id: int, result) -> None: ...
    def save_trust(self, incident_id: int, trust, action: str) -> None: ...
    def save_duplicates(self, incident_id: int, results) -> None: ...
    def save_allocation(self, incident_id: int, allocation) -> None: ...
    def mark_stage_failed(self, incident_id: int, stage: str, error: str) -> None: ...
    def mark_done(self, incident_id: int) -> None: ...


@dataclass
class Job:
    incident_id: int
    text: str
    has_gps: bool = False
    trust_inputs: TrustInputs = field(default_factory=TrustInputs)
    available_vehicles: Callable[[], list[Vehicle]] = lambda: []
    duplicate_candidates: Callable[[], list[Candidate]] = lambda: []   # from the SQL gate query (type, 300 m, 15 min)


def run_pipeline(job: Job, store: Store, llm: LLMClient) -> list[str]:
    """Returns the list of stages that ran. The original report is never touched here."""
    ran: list[str] = []
    try:
        triage = run_triage(job.text, llm, job.has_gps)
    except TriageFailed as exc:
        store.mark_stage_failed(job.incident_id, "triage", str(exc))      # -> needs_check + ai_failed (manual mode)
        return ran
    store.save_triage(job.incident_id, triage); ran.append("triage")

    ti = replace(job.trust_inputs, has_real_details=triage.has_real_details,
                 vague_or_joking=triage.vague_or_joking)
    trust = score_report(ti)
    severity = triage.severity or "medium"                      # unknown severity is treated cautiously, not as low
    action = decide_action(trust.tier, severity)
    store.save_trust(job.incident_id, trust, action); ran.append("trust")

    # Duplicate check runs for every report (it also helps the dispatcher judge a doubtful one).
    store.save_duplicates(job.incident_id, best_candidates(job.duplicate_candidates())); ran.append("coordination")

    # D-021 (proposed): low tier + low/medium severity waits for the dispatcher; urgent reports never wait.
    if action == "review_queue" and severity not in URGENT:
        store.mark_done(job.incident_id)
        return ran
    need = vehicles_needed(triage.incident_type or "other", severity, triage.victims_estimate)
    store.save_allocation(job.incident_id, rank(job.available_vehicles(), need)); ran.append("allocation")
    store.mark_done(job.incident_id)
    return ran
```

### LangGraph wiring — **NOT VERIFIED (library not installed here)**

```python
# backend/app/agents/orchestrator.py  (illustrative; confirm the current LangGraph API when B1-A2-13 starts)
from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipelineState(TypedDict, total=False):
    incident_id: int
    is_voice: bool
    triage: dict
    trust: dict
    action: str
    error: str

def build_graph(nodes) -> "CompiledGraph":
    g = StateGraph(PipelineState)
    for name in ("stt", "geocode", "triage", "trust_policy", "coordination", "allocation"):
        g.add_node(name, getattr(nodes, name))          # each node saves through pipeline_store, then returns state
    g.set_conditional_entry_point(lambda s: "stt" if s["is_voice"] else "geocode",
                                  {"stt": "stt", "geocode": "geocode"})
    g.add_edge("stt", "geocode")
    g.add_edge("geocode", "triage")
    g.add_conditional_edges("triage", lambda s: "failed" if s.get("error") else "ok",
                            {"ok": "trust_policy", "failed": END})      # failure already recorded by the node
    g.add_edge("trust_policy", "coordination")
    g.add_conditional_edges("coordination", nodes.needs_allocation,      # False for low trust + low/medium severity
                            {True: "allocation", False: END})
    g.add_edge("allocation", END)
    return g.compile()
```

Separate small graphs handle the `reallocate` job (allocation only) and `retrust` job (trust and policy only, after a caller confirmation).

### How the agents exchange information

| From → to | What is passed | Where it lives |
|---|---|---|
| API → worker | "a new record is pending" | `incidents.pipeline_state` + NOTIFY `report_pending` |
| Worker stage → next stage | typed state (C-2 objects) | in memory during the job |
| Each stage → database | validated result | `pipeline_store` (C-6) → `incidents`, `duplicate_candidates`, `recommendations` |
| Worker → dashboard | event name + incident id | NOTIFY `incident_events` → API → WebSocket |
| Dispatcher → agents | edits, decisions | API writes `pipeline_state='reallocate'` / `retrust`; worker picks up |

## 6.8 Error handling summary

| Failure | Detection | Result |
|---|---|---|
| LLM down or too slow | timeout 8 s, retries ≤ 2 | `needs_check` + `ai_failed`, banner, manual dispatch |
| LLM returns invalid JSON | schema validation, one retry | same as above if the second attempt fails |
| Speech-to-text fails | exception or very low log-prob | `needs_check` + `stt_failed`, audio playable |
| Geocoder finds nothing | no match | `location_source = unknown`, warning (TC-03); GPS used if present |
| OSRM down | timeout 1.5 s | straight-line ETA marked approximate (TC-20) |
| Worker crash mid-job | stale `processing` row | reset to `pending` and re-run; completed stages already saved |
| Database down | write error | job not marked done; API returns 503 on intake |

## 6.9 Testing strategy for the agents

| Level | What | Tool |
|---|---|---|
| Unit, no network | schemas, scorer, policy, scoring, allocation, triage with `FakeLLMClient`, pipeline with `FakePipelineStore` | pytest — **sketch versions pass now** |
| Contract | same JSON fixtures loaded by Agent 1 (storage) and Agent 3 (display) | pytest/Jest |
| Integration | real `pipeline_store` on PostGIS, real OSRM container, FakeLLM | pytest `@pytest.mark.db` (B2-01) |
| Evaluation | real model on labelled sets: type, severity, victims, language, latency p50/p95, duplicate recall and wrong-merge rate, WER, ETA error | `tests/ai_eval/run_eval.py` (B1-A2-17, B8) |
| Safety property tests | urgent never held; fake never dispatched; agents cannot write vehicles | pytest |

## 6.10 What an agent must never do

- Dispatch, lock, assign or release a vehicle.
- Mark a report **fake** (only a dispatcher can, UC-07).
- Merge incidents below 85 % match, change an incident's status when linking, or delete a report.
- Overwrite `original_text` / `audio_ref`, or overwrite AI values with dispatcher edits (both are kept).
- Use caller identity or history inside an LLM prompt.
- Present an approximate ETA as accurate.
