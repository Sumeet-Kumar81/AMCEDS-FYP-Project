"""vehicles, vehicle_locations and hospitals (SDS v1.1 Tables 5.5, 5.6, 5.9). Task B1-A1-09.

A driver drives at most one vehicle (``vehicles.driver_id`` unique when set; SDS Table 2.2 one-to-one).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._common import TZ, one_of, point
from app.schemas.enums import VehicleStatus, VehicleType


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        one_of("vehicle_type", VehicleType),
        one_of("status", VehicleStatus),
        CheckConstraint("patient_capacity >= 0", name="patient_capacity_not_negative"),
        Index("uq_vehicles_driver_id", "driver_id", unique=True, postgresql_where=text("driver_id IS NOT NULL")),
    )

    vehicle_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    vehicle_type: Mapped[str] = mapped_column(Text, nullable=False)
    plate_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    station_name: Mapped[str | None] = mapped_column(Text)
    patient_capacity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'available'"))
    last_location: Mapped[Any] = mapped_column(point(), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(TZ)


class VehicleLocation(Base):
    __tablename__ = "vehicle_locations"
    __table_args__ = (
        CheckConstraint("speed_kmh IS NULL OR speed_kmh >= 0", name="speed_not_negative"),
        Index("ix_vehicle_locations_vehicle_time", "vehicle_id", text("recorded_at DESC")),
    )

    location_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.vehicle_id"), nullable=False)
    location: Mapped[Any] = mapped_column(point(spatial_index=False), nullable=False)
    speed_kmh: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    recorded_at: Mapped[datetime] = mapped_column(TZ, nullable=False)


class Hospital(Base):
    __tablename__ = "hospitals"

    hospital_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[Any] = mapped_column(point(), nullable=False)
    departments: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
