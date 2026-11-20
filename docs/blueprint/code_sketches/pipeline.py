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
