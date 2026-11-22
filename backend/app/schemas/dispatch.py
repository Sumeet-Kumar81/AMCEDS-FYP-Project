"""Dispatch approval request and the vehicle list for dispatchers (B1-A1-25; SRS UC-06 3–4, 3a, 4a).

``DispatchIn`` is the body of ``POST /api/v1/incidents/{incident_id}/dispatch``; ``VehicleOut`` is one
row of ``GET /api/v1/vehicles`` (manual dispatch and "pick another vehicle").
"""
from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.schemas.assignment import DeclineReason, TripStatus
from app.schemas.enums import VehicleStatus, VehicleType

MAX_VEHICLES_PER_DISPATCH = 10


class DispatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_ids: list[int] = Field(min_length=1, max_length=MAX_VEHICLES_PER_DISPATCH)
    hospital_id: int | None = Field(default=None, ge=1)
    override_reason: str | None = Field(default=None, max_length=500,
                                        description="Why the dispatcher chose differently from the AI (optional)")

    @field_validator("vehicle_ids")
    @classmethod
    def _unique_positive(cls, ids: list[int]) -> list[int]:
        if any(i < 1 for i in ids):
            raise ValueError("vehicle ids are positive numbers")
        if len(set(ids)) != len(ids):
            raise ValueError("each vehicle may be listed once")
        return ids

    @field_validator("override_reason", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value


class VehicleOut(BaseModel):
    """A vehicle as the dispatcher needs it to choose. ``can_dispatch`` = status available, a driver
    on duty and no open assignment. GPS older than ``signal_lost_s`` is ``signal_lost`` (a warning only)."""

    model_config = ConfigDict(extra="forbid")

    vehicle_id: int
    plate_number: str
    vehicle_type: VehicleType
    status: VehicleStatus
    station_name: str | None = None
    patient_capacity: int = Field(ge=0)
    driver_id: int | None = None
    driver_name: str | None = None
    driver_on_duty: bool
    lat: float | None = None
    lon: float | None = None
    last_seen_at: AwareDatetime | None = None
    signal_lost: bool
    has_open_assignment: bool
    can_dispatch: bool
    #: straight-line distance to the incident, only when ``incident_id`` was given and both places are known
    distance_meters: int | None = Field(default=None, ge=0)
    distance_is_approximate: bool = True


# ---------------------------------------------------------------- assignment lifecycle (B1-A1-26)
class DeclineIn(BaseModel):
    """Driver: "Cannot go", with a reason from the list (UC-08 2a)."""
    model_config = ConfigDict(extra="forbid")
    reason: DeclineReason


class TripStatusIn(BaseModel):
    """Driver: the next trip step (UC-09): on_scene, picked_up, at_hospital or available."""
    model_config = ConfigDict(extra="forbid")
    status: TripStatus


class CancelIn(BaseModel):
    """Dispatcher: stop an open assignment and free the vehicle."""
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return (value.strip() or None) if isinstance(value, str) else value


class HospitalChangeIn(BaseModel):
    """Dispatcher: send an open assignment to another hospital (UC-09 2a)."""
    model_config = ConfigDict(extra="forbid")
    hospital_id: int = Field(ge=1)
