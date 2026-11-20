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
