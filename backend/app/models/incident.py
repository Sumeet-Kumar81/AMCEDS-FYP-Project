"""incidents and incident_groups (SDS v1.1 Tables 5.2 and 5.3, with the D-004 columns). Task B1-A1-08.

Safety rules enforced by the database (not only by the services):
  * ``reference_no`` is computed by PostgreSQL from ``incident_id`` (``INC-`` + at least six digits),
    so a reference number exists only for a row that was really saved (NFR-P12).
  * A record has the report text or the audio (or both).
  * ``original_text`` and ``audio_ref`` can be set once and never changed afterwards (trigger
    ``incidents_keep_original`` in migration 0002). A voice report gets its transcript once.
  * Allowed values follow D-005 / contract C-1; ``confidence`` 0..1; ``trust_score`` 0..100.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Computed,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ, one_of, point
from app.schemas.enums import Channel, IncidentStatus, IncidentType, LocationSource, PipelineState, Severity, TrustTier

REFERENCE_NO_SQL = (
    "'INC-' || CASE WHEN incident_id < 1000000 THEN lpad(incident_id::text, 6, '0') ELSE incident_id::text END"
)
GROUP_STATUSES = ("open", "closed")  # SDS Table 5.3


class IncidentGroup(Base):
    __tablename__ = "incident_groups"
    __table_args__ = (
        one_of("status", GROUP_STATUSES),
        CheckConstraint("report_count >= 0", name="report_count_not_negative"),
    )

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        one_of("channel", Channel),
        one_of("location_source", LocationSource),
        one_of("incident_type", IncidentType),
        one_of("severity", Severity),
        one_of("trust_tier", TrustTier),
        one_of("status", IncidentStatus),
        one_of("pipeline_state", PipelineState),
        CheckConstraint("original_text IS NOT NULL OR audio_ref IS NOT NULL", name="has_text_or_audio"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_0_to_1"),
        CheckConstraint("trust_score IS NULL OR (trust_score >= 0 AND trust_score <= 100)", name="trust_score_0_to_100"),
        CheckConstraint("victims_estimate IS NULL OR victims_estimate >= 0", name="victims_not_negative"),
        CheckConstraint("pipeline_attempts >= 0", name="pipeline_attempts_not_negative"),
        Index("ix_incidents_status_severity", "status", "severity"),
        Index("ix_incidents_type_received_at", "incident_type", "received_at"),
        Index(
            "ix_incidents_pipeline_waiting",
            "pipeline_state",
            postgresql_where=text("pipeline_state IN ('pending', 'reallocate')"),
        ),
    )

    incident_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    reference_no: Mapped[str] = mapped_column(Text, Computed(REFERENCE_NO_SQL, persisted=True), unique=True)
    client_request_id: Mapped[str | None] = mapped_column(Text, unique=True)
    caller_id: Mapped[int | None] = mapped_column(ForeignKey("callers.caller_id"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("incident_groups.group_id"), index=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    original_text: Mapped[str | None] = mapped_column(Text)
    audio_ref: Mapped[str | None] = mapped_column(Text)
    reporter_name: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    location: Mapped[Any] = mapped_column(point(), nullable=True)
    location_text: Mapped[str | None] = mapped_column(Text)
    location_source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unknown'"))
    caller_gps: Mapped[Any] = mapped_column(point(spatial_index=False), nullable=True)
    incident_type: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    victims_estimate: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    trust_score: Mapped[int | None] = mapped_column(Integer)
    trust_tier: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    review_reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    ai_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    trust_signals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    allocation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    pipeline_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    pipeline_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pipeline_error: Mapped[str | None] = mapped_column(Text)
    pipeline_updated_at: Mapped[datetime | None] = mapped_column(TZ)
