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
