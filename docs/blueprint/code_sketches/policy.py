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
