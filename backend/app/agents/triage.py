"""Triage Agent (SRS UC-02, F2; SDS Table 4.1, Table 6.3 TriageAgent). Task B1-A2-03.

Reads one report through the LLM Gateway and returns a C-2 ``TriageResult``.

* The prompt is versioned (``prompts/triage_v1.md``); its few-shot examples are SIMULATED.
* Only the expected keys are taken from the model; anything else it says (e.g. "status" or
  "dispatch") is dropped, so model output can never set a status or dispatch a vehicle.
* Unknown values stay ``None``; a location is never guessed.
* Invalid output (not JSON, wrong type, out of range, missing key) -> ONE retry with the error shown
  to the model; still invalid -> ``TriageFailed`` (the orchestrator puts the report in manual mode).
  Transient errors (timeout, connection, HTTP 429/5xx) are raised unchanged: the orchestrator retries.
* A script check (Arabic script vs Latin letters) gives a language hint and the fallback when the
  model gives no language.
* Deterministic post-rule: ``missing_fields`` lists ``incident_type`` and/or ``location`` when the
  report does not give them (UC-02 2a). The low-confidence check (UC-02 4a) is applied when the result
  is saved, against the incident's own ``triage_min_confidence`` (C-6 ``save_triage``).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.llm.gateway import LLMClient, LLMError
from app.schemas.ai import TriageInput, TriageResult

PROMPT_VERSION = "triage_v1"
PROMPTS = Path(__file__).parent / "prompts"

MODEL_KEYS = (
    "language", "language_confidence", "incident_type", "type_confidence", "severity", "severity_confidence",
    "victims_estimate", "victims_confidence", "location_words", "has_real_details", "vague_or_joking",
    "overall_confidence",
)
_NULL_WORDS = {"", "null", "none", "unknown", "n/a", "not stated", "not mentioned"}
_LANGUAGES = {
    "english": "English", "en": "English",
    "urdu": "Urdu", "ur": "Urdu",
    "sindhi": "Sindhi", "sd": "Sindhi",
    "roman urdu": "Roman Urdu", "roman-urdu": "Roman Urdu", "roman_urdu": "Roman Urdu",
    "mixed": "Mixed",
}
# Letters used in Sindhi but not in Urdu (Arabic-script Sindhi alphabet).
_SINDHI_ONLY = set("ڄڃڇڏڊڌڍڙڳڱٻٽٿڦڻڪ")


class TriageFailed(Exception):
    """The model output could not be validated after one retry. The report goes to manual mode."""


@lru_cache
def load_prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS / f"{version}.md").read_text(encoding="utf-8")


def _is_arabic_script(ch: str) -> bool:
    o = ord(ch)
    return 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF


def script_language(text: str) -> str | None:
    """Language hint from the writing system. Latin text returns ``None``: English and Roman Urdu use the
    same letters, so only the model can tell them apart."""
    arabic = [ch for ch in text if ch.isalpha() and _is_arabic_script(ch)]
    latin = [ch for ch in text if ch.isascii() and ch.isalpha()]
    total = len(arabic) + len(latin)
    if total == 0:
        return None
    if len(arabic) / total >= 0.8:
        return "Sindhi" if any(ch in _SINDHI_ONLY for ch in arabic) else "Urdu"
    if len(latin) / total >= 0.8:
        return None
    return "Mixed"


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in MODEL_KEYS if k not in data]
    if missing:
        raise ValueError(f"missing keys: {', '.join(missing)}")
    out = {k: data[k] for k in MODEL_KEYS}
    for key in ("language", "incident_type", "severity", "location_words"):
        if isinstance(out[key], str):
            value = out[key].strip()
            out[key] = None if value.lower() in _NULL_WORDS else value
    for key in ("incident_type", "severity"):
        if isinstance(out[key], str):
            out[key] = out[key].lower()
    if isinstance(out["language"], str):
        out["language"] = _LANGUAGES.get(out["language"].lower(), out["language"])
    return out


def _short(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]]
        return "; ".join(parts)
    return str(exc)[:300]


class TriageAgent:
    def __init__(self, llm: LLMClient, prompt_version: str = PROMPT_VERSION) -> None:
        self.llm = llm
        self.prompt_version = prompt_version
        self.system = load_prompt(prompt_version)

    @staticmethod
    def user_message(inp: TriageInput, hint: str | None) -> str:
        lines = [f"Report: {inp.text!r}"]
        if inp.location_text:
            lines.append(f"Location typed by the caller in the form: {inp.location_text!r}")
        if hint:
            lines.append(f"Writing system suggests the language: {hint}")
        return "\n".join(lines)

    async def run(self, inp: TriageInput, *, transcript_unclear: bool = False) -> TriageResult:
        hint = inp.language_hint or script_language(inp.text)
        base = self.user_message(inp, hint)
        error: str | None = None
        for _attempt in range(2):
            message = base if error is None else (
                f"{base}\n\nYour previous answer was rejected: {error}\nReturn the corrected JSON object only.")
            try:
                reply = await self.llm.complete_json(self.system, message)
            except LLMError as exc:
                if exc.transient:
                    raise
                error = str(exc)
                continue
            try:
                return self._result(reply.data, reply.model, reply.latency_ms, inp, hint, transcript_unclear)
            except (ValidationError, ValueError, TypeError) as exc:
                error = _short(exc)
        raise TriageFailed(f"invalid model output twice: {error}")

    def _result(self, data: dict[str, Any], model: str, latency_ms: int, inp: TriageInput, hint: str | None,
                transcript_unclear: bool) -> TriageResult:
        fields = _clean(data)
        if fields["language"] is None and hint:
            fields["language"], fields["language_confidence"] = hint, None
        located = fields["location_words"] or inp.location_text or inp.caller_gps
        missing = [name for name, absent in (("incident_type", fields["incident_type"] is None),
                                             ("location", not located)) if absent]
        return TriageResult.model_validate({
            **fields, "missing_fields": missing, "transcript_unclear": transcript_unclear,
            "model": model, "prompt_version": self.prompt_version, "latency_ms": max(0, int(latency_ms)),
        })
