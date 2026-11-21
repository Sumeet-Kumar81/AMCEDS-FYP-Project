"""recommendations and assignments (SDS v1.1 Tables 5.7 and 5.8, with the D-004 columns). Task B1-A1-10.

Double-dispatch guard (NFR-S6): a vehicle has at most ONE open assignment. Enforced by the partial
unique index ``uq_assignments_open_vehicle`` on ``assignments(vehicle_id)`` where the status is
open. "Open" is exactly C-7 ``OPEN_ASSIGNMENT_STATUSES`` (approved, accepted).

Human in the loop (NFR-S1): every assignment names the dispatcher who approved it
(``approved_by`` NOT NULL). Recommendations never lock anything.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ, one_of
from app.schemas.assignment import OPEN_ASSIGNMENT_STATUSES
from app.schemas.enums import AssignmentStatus, VehicleType

OPEN_STATUSES_SQL = ", ".join(f"'{s.value}'" for s in sorted(OPEN_ASSIGNMENT_STATUSES))


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        one_of("vehicle_type", VehicleType),
        CheckConstraint("rank >= 1", name="rank_from_1"),
        CheckConstraint("eta_seconds >= 0 AND distance_meters >= 0", name="eta_distance_not_negative"),
        CheckConstraint("batch_no >= 1", name="batch_from_1"),
        Index("ix_recommendations_incident_current", "incident_id", "is_current"),
    )

    rec_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.incident_id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.vehicle_id"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    vehicle_type: Mapped[str] = mapped_column(Text, nullable=False)
    eta_is_approximate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_spare: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    route_geometry: Mapped[str | None] = mapped_column(Text)
    batch_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        one_of("status", AssignmentStatus),
        Index(
            "uq_assignments_open_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text(f"status IN ({OPEN_STATUSES_SQL})"),
        ),
    )

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.incident_id"), nullable=False, index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.vehicle_id"), nullable=False)
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.hospital_id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'approved'"))
    approved_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(TZ)
    on_scene_at: Mapped[datetime | None] = mapped_column(TZ)
    picked_up_at: Mapped[datetime | None] = mapped_column(TZ)
    at_hospital_at: Mapped[datetime | None] = mapped_column(TZ)
    completed_at: Mapped[datetime | None] = mapped_column(TZ)
    notified_at: Mapped[datetime | None] = mapped_column(TZ)
    decline_reason: Mapped[str | None] = mapped_column(Text)
    declined_at: Mapped[datetime | None] = mapped_column(TZ)
    timed_out_at: Mapped[datetime | None] = mapped_column(TZ)
