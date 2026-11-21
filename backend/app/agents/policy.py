"""Trust tier × severity → what happens next (SRS Appendix C, Table 7.3.2). Task B1-A2-07. No LLM.

| Trust tier | Low or medium severity          | High or critical severity                      |
|------------|---------------------------------|------------------------------------------------|
| High       | continue                        | continue                                       |
| Medium     | continue and ask for confirmation (it runs at the same time, it never blocks)   |
| Low        | review queue (UC-07)            | urgent with warning: stays in the main queue,  |
|            |                                 | vehicles recommended at once, dispatch allowed |

Safety rule 3: a high or critical report is never held back by the trust check. A report whose
severity is unknown (for example because the Triage AI failed) is treated as possibly critical, so
it is never held back either.

D-021 (approved 2026-11-21): vehicles are not recommended for a ``review_queue`` report until the
dispatcher marks it Real; every other action gets a recommendation at once.
"""
from __future__ import annotations

from app.schemas.ai import TrustAction
from app.schemas.enums import Severity, TrustTier

URGENT_SEVERITIES = frozenset({Severity.HIGH, Severity.CRITICAL})


def is_urgent(severity: Severity | str | None) -> bool:
    """High, critical or unknown: never held back."""
    return severity is None or Severity(severity) in URGENT_SEVERITIES


def decide_action(tier: TrustTier | str, severity: Severity | str | None) -> TrustAction:
    tier = TrustTier(tier)
    if tier is TrustTier.HIGH:
        return TrustAction.CONTINUE
    if tier is TrustTier.MEDIUM:
        return TrustAction.CONTINUE_AND_CONFIRM
    return TrustAction.URGENT_WITH_WARNING if is_urgent(severity) else TrustAction.REVIEW_QUEUE


def allocate_now(action: TrustAction | str) -> bool:
    """D-021: recommend vehicles now, except for a report waiting in the review queue."""
    return TrustAction(action) is not TrustAction.REVIEW_QUEUE
