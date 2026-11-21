"""duplicate_candidates and confirmation_requests (SDS v1.1 Tables 5.12 and 5.13, D-004). Task B1-A1-11."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ, one_of
from app.schemas.enums import DuplicateDecision

CONFIRMATION_CHANNELS = ("sms", "app")  # SDS Table 5.13
CONFIRMATION_RESPONSES = ("confirmed", "denied", "none")  # SDS Table 5.13


class DuplicateCandidate(Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        one_of("decision", DuplicateDecision),
        CheckConstraint("match_confidence >= 0 AND match_confidence <= 100", name="match_confidence_0_to_100"),
        CheckConstraint("similarity IS NULL OR (similarity >= 0 AND similarity <= 1)", name="similarity_0_to_1"),
        CheckConstraint("distance_m IS NULL OR distance_m >= 0", name="distance_not_negative"),
        CheckConstraint("time_diff_s IS NULL OR time_diff_s >= 0", name="time_diff_not_negative"),
        CheckConstraint("incident_id <> candidate_incident_id", name="not_itself"),
        UniqueConstraint("incident_id", "candidate_incident_id"),
    )

    duplicate_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.incident_id"), nullable=False)
    candidate_incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.incident_id"), nullable=False, index=True)
    match_confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    time_diff_s: Mapped[int | None] = mapped_column(Integer)
    similarity: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))  # empty if automatic
    decided_at: Mapped[datetime | None] = mapped_column(TZ)


class ConfirmationRequest(Base):
    __tablename__ = "confirmation_requests"
    __table_args__ = (one_of("channel", CONFIRMATION_CHANNELS), one_of("response", CONFIRMATION_RESPONSES))

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.incident_id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)  # only the hash of the one-time code is stored
    sent_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    response: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'none'"))
    responded_at: Mapped[datetime | None] = mapped_column(TZ)
