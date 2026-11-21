"""audit_logs, settings and worker_heartbeats (SDS v1.1 Tables 5.10, 5.11, 5.15). Task B1-A1-11.

``audit_logs`` rows can never be changed or deleted: trigger ``audit_logs_no_modify`` in migration
0002 raises on UPDATE and DELETE (NFR-C10). ``details`` is JSONB (D-004) so "what the AI suggested
and what was chosen" is queryable.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_incident_time", "incident_id", "created_at"),)

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))  # empty for system actions
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.incident_id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())


class Setting(Base):
    """Admin-configurable business rules (SRS Appendix C). Values are text; the settings service
    (B1-A1-12) validates ranges and types."""

    __tablename__ = "settings"

    setting_key: Mapped[str] = mapped_column(Text, primary_key=True)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    updated_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    info: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
