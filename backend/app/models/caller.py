"""callers (SDS v1.1 Table 5.1). Task B1-A1-07.

A caller is identified by phone number or device id; each is unique when present.
``real_count`` / ``fake_count`` / ``flagged_until`` feed the Trust Scorer (SRS Table 7.3.1).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ


class Caller(Base):
    __tablename__ = "callers"
    __table_args__ = (
        CheckConstraint("real_count >= 0 AND fake_count >= 0", name="counts_not_negative"),
        Index("uq_callers_phone_number", "phone_number", unique=True, postgresql_where=text("phone_number IS NOT NULL")),
        Index("uq_callers_device_id", "device_id", unique=True, postgresql_where=text("device_id IS NOT NULL")),
    )

    caller_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str | None] = mapped_column(Text)
    device_id: Mapped[str | None] = mapped_column(Text)
    real_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    fake_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_report_at: Mapped[datetime | None] = mapped_column(TZ)
    flagged_until: Mapped[datetime | None] = mapped_column(TZ)
