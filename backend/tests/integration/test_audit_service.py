"""Audit service tests (B1-A1-13): the audit row and the business change commit or roll back together."""
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Incident
from app.services.audit import AuditAction, record

pytestmark = pytest.mark.db


async def count(session: AsyncSession, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_record_writes_one_row_with_json_details(db_session: AsyncSession) -> None:
    incident = Incident(channel="web", original_text="SIMULATED report")
    db_session.add(incident)
    await db_session.flush()
    log_id = await record(db_session, AuditAction.REPORT_RECEIVED, incident_id=incident.incident_id,
                          details={"channel": "web", "suggested": [5, 8], "chosen": [5]})
    row = await db_session.get(AuditLog, log_id)
    assert row.action == "report.received" and row.details["chosen"] == [5] and row.created_at.tzinfo


async def test_rolling_back_the_change_rolls_back_its_audit_row(db_session: AsyncSession) -> None:
    before = (await count(db_session, Incident), await count(db_session, AuditLog))
    with pytest.raises(RuntimeError):
        async with db_session.begin_nested():
            incident = Incident(channel="web", original_text="SIMULATED report")
            db_session.add(incident)
            await db_session.flush()
            await record(db_session, AuditAction.REPORT_RECEIVED, incident_id=incident.incident_id)
            raise RuntimeError("the business step failed after the audit row was written")
    assert (await count(db_session, Incident), await count(db_session, AuditLog)) == before


async def test_a_failing_audit_row_stops_the_business_change(db_session: AsyncSession) -> None:
    """No audit = no commit: an audit row that cannot be saved rolls the change back with it."""
    before = (await count(db_session, Incident), await count(db_session, AuditLog))
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(Incident(channel="web", original_text="SIMULATED report"))
            await db_session.flush()
            await record(db_session, AuditAction.AI_TRIAGE, incident_id=999_999_999)  # no such incident
    assert (await count(db_session, Incident), await count(db_session, AuditLog)) == before


@pytest.mark.parametrize("details", [{"when": object()}, {"x": float("nan")}])
async def test_details_must_be_json(db_session: AsyncSession, details: dict) -> None:
    with pytest.raises((TypeError, ValueError)):
        await record(db_session, AuditAction.AI_TRIAGE, details=details)


async def test_unknown_action_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await record(db_session, "something.made_up")  # type: ignore[arg-type]


def test_action_catalogue_covers_the_plan() -> None:
    planned = {"report.received", "ai.triage", "ai.trust", "ai.duplicates", "ai.allocation", "incident.edited",
               "duplicate.confirmed", "review.decision", "dispatch.approved", "vehicle.locked", "vehicle.unlocked",
               "settings.changed", "auth.login_failed", "auth.locked"}
    values = {a.value for a in AuditAction}
    assert planned <= values
    assert any(v.startswith("assignment.") for v in values) and any(v.startswith("user.") for v in values)
