"""Resource Allocation Agent (SRS UC-05, Appendix C Table 7.3.3; D-019). Task B1-A2-11. No LLM.

Decides which vehicle types and how many are needed, then ranks the available vehicles by ETA.
The list is the needed vehicles plus ``spare_vehicles`` spares (2 in total, D-019). It only
recommends: it never writes to the database and never locks a vehicle (safety rule 6); the
vehicles it gets are already the available ones (C-6 ``list_available_vehicles``).

Vehicle rules (Table 7.3.3 + D-019, approved 2026-11-21):
  * accident: ambulances = victims ÷ ``patients_per_ambulance`` rounded up, at least 1; + 1 backup if
    critical. An accident with 0 victims still gets 1 ambulance and a "please check" flag.
  * fire: 1 fire truck + ambulances by the same rule + 1 backup.
  * medical: ambulances by the same rule, at least 1.
  * other, or type unknown: no automatic type; every available vehicle, nearest first, and the
    dispatcher chooses.
  * victims unknown: 1 vehicle of each needed type and the "please check" flag.
  The flag is ``victims_unknown_check`` (C-2): "the dispatcher must check the number of victims".

ETAs come from an ``EtaProvider``. Until OSRM routing exists (B1-A2-10) the provider is
``StraightLineEta``: straight-line distance at ``fallback_speed_kmh``, always marked approximate
(safety rule 7). Ties are broken by distance, then vehicle id, so the result is repeatable.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from app.schemas.ai import AllocationResult, RoutingMode, VehicleRecommendation
from app.schemas.enums import IncidentType, Severity, VehicleType
from app.services.pipeline_store import VehicleRow
from app.services.settings import REGISTRY

EARTH_RADIUS_M = 6_371_000


@dataclass(frozen=True)
class AllocationInput:
    incident_type: IncidentType | None
    severity: Severity | None
    victims: int | None
    lat: float | None
    lon: float | None


@dataclass(frozen=True)
class Eta:
    seconds: int
    meters: int
    approximate: bool


class EtaProvider(Protocol):
    mode: RoutingMode

    async def eta(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Eta: ...


def straight_line_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle (haversine) distance in metres."""
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


class StraightLineEta:
    """Fallback ETA (UC-05 5a): straight-line distance at a fixed speed, labelled approximate."""

    mode = RoutingMode.STRAIGHT_LINE

    def __init__(self, speed_kmh: float) -> None:
        if speed_kmh <= 0:
            raise ValueError("speed must be positive")
        self.speed_ms = speed_kmh / 3.6

    async def eta(self, from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> Eta:
        meters = straight_line_m(from_lat, from_lon, to_lat, to_lon)
        return Eta(seconds=round(meters / self.speed_ms), meters=round(meters), approximate=True)


@dataclass(frozen=True)
class Needed:
    counts: dict[VehicleType, int]
    check_victims: bool
    dispatcher_chooses: bool


def vehicles_needed(incident_type: IncidentType | str | None, severity: Severity | str | None,
                    victims: int | None, patients_per_ambulance: int) -> Needed:
    """Table 7.3.3 + D-019. Pure function."""
    if incident_type is None or IncidentType(incident_type) is IncidentType.OTHER:
        return Needed({}, check_victims=False, dispatcher_chooses=True)
    kind = IncidentType(incident_type)
    unknown = victims is None
    ambulances = 1 if unknown else max(1, math.ceil(victims / patients_per_ambulance))
    check = unknown or (kind is IncidentType.ACCIDENT and victims == 0)
    if kind is IncidentType.ACCIDENT:
        counts = {VehicleType.AMBULANCE: ambulances}
        if severity is not None and Severity(severity) is Severity.CRITICAL:
            counts[VehicleType.BACKUP] = 1
    elif kind is IncidentType.FIRE:
        counts = {VehicleType.FIRE_TRUCK: 1, VehicleType.AMBULANCE: ambulances, VehicleType.BACKUP: 1}
    else:  # medical
        counts = {VehicleType.AMBULANCE: ambulances}
    return Needed(counts, check_victims=check, dispatcher_chooses=False)


@dataclass(frozen=True)
class _Ranked:
    vehicle: VehicleRow
    eta: Eta

    @property
    def key(self) -> tuple[int, int, int]:
        return self.eta.seconds, self.eta.meters, self.vehicle.vehicle_id


class ResourceAllocationAgent:
    def __init__(self, eta_provider: EtaProvider | None = None) -> None:
        self._eta = eta_provider

    def _provider(self, settings: Mapping[str, int | float]) -> EtaProvider:
        if self._eta is not None:
            return self._eta
        return StraightLineEta(float(settings.get("fallback_speed_kmh", REGISTRY["fallback_speed_kmh"].default)))

    async def run(self, incident: AllocationInput, vehicles: list[VehicleRow],
                  settings: Mapping[str, int | float] | None = None) -> AllocationResult:
        settings = settings or {}
        per_ambulance = int(settings.get("patients_per_ambulance", REGISTRY["patients_per_ambulance"].default))
        spares = int(settings.get("spare_vehicles", REGISTRY["spare_vehicles"].default))
        need = vehicles_needed(incident.incident_type, incident.severity, incident.victims, per_ambulance)
        provider = self._provider(settings)

        if incident.lat is None or incident.lon is None:  # no place to measure from: the dispatcher locates first
            return AllocationResult(needed=need.counts, victims_unknown_check=need.check_victims,
                                    shortage=self._shortage(need, {}), recommendations=[], routing_mode=provider.mode)

        ranked = [
            _Ranked(v, await provider.eta(v.lat, v.lon, incident.lat, incident.lon))
            for v in vehicles
            if need.dispatcher_chooses or VehicleType(v.vehicle_type) in need.counts
        ]
        ranked.sort(key=lambda r: r.key)

        if need.dispatcher_chooses:
            chosen, spare = ranked, []
        else:
            chosen, used = [], set()
            for vtype, n in need.counts.items():
                pool = [r for r in ranked if VehicleType(r.vehicle.vehicle_type) is vtype][:n]
                chosen += pool
                used.update(r.vehicle.vehicle_id for r in pool)
            chosen.sort(key=lambda r: r.key)
            spare = [r for r in ranked if r.vehicle.vehicle_id not in used][:spares]

        spare_ids = {r.vehicle.vehicle_id for r in spare}
        available = {t: sum(1 for r in ranked if VehicleType(r.vehicle.vehicle_type) is t) for t in need.counts}
        recommendations = [
            VehicleRecommendation(vehicle_id=r.vehicle.vehicle_id, vehicle_type=r.vehicle.vehicle_type, rank=i,
                                  eta_seconds=r.eta.seconds, distance_meters=r.eta.meters,
                                  eta_is_approximate=r.eta.approximate, is_spare=r.vehicle.vehicle_id in spare_ids)
            for i, r in enumerate(chosen + spare, start=1)
        ]
        return AllocationResult(needed=need.counts, victims_unknown_check=need.check_victims,
                                shortage=self._shortage(need, available), recommendations=recommendations,
                                routing_mode=provider.mode)

    @staticmethod
    def _shortage(need: Needed, available: Mapping[VehicleType, int]) -> dict[VehicleType, int] | None:
        """Types with fewer available vehicles than needed → how many are available (TC-19)."""
        short = {t: available.get(t, 0) for t, n in need.counts.items() if available.get(t, 0) < n}
        return short or None
