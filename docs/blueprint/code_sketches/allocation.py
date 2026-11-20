"""Vehicle counts (SRS Table 7.3.3) and ETA ranking. D-019 points are PROPOSED. Real file: backend/app/agents/resource.py (named allocation here only because "resource" is a Python standard-library name)"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Needed:
    counts: dict[str, int]                 # e.g. {"ambulance": 3}
    victims_unknown: bool = False          # dispatcher must check (TC-17)
    dispatcher_chooses: bool = False       # incident type "other"


def vehicles_needed(incident_type: str, severity: str, victims: int | None,
                    patients_per_ambulance: int = 2) -> Needed:
    unknown = victims is None
    amb = 1 if unknown else max(1, math.ceil(victims / patients_per_ambulance))
    if incident_type == "accident":
        c = {"ambulance": amb}
        if severity == "critical":
            c["backup"] = 1
        return Needed(c, victims_unknown=unknown)
    if incident_type == "fire":
        return Needed({"fire_truck": 1, "ambulance": amb, "backup": 1}, victims_unknown=unknown)
    if incident_type == "medical":
        return Needed({"ambulance": amb}, victims_unknown=unknown)
    return Needed({}, dispatcher_chooses=True)


@dataclass(frozen=True)
class Vehicle:
    vehicle_id: int
    vehicle_type: str
    eta_s: float
    distance_m: float
    eta_approximate: bool = False


@dataclass
class Allocation:
    chosen: list[Vehicle] = field(default_factory=list)
    spare: list[Vehicle] = field(default_factory=list)
    shortage: dict[str, int] = field(default_factory=dict)    # type -> how many are free
    victims_unknown: bool = False


def rank(available: list[Vehicle], need: Needed, spare_count: int = 2) -> Allocation:
    """`available` must already exclude vehicles that are locked or not on duty.
    Nothing here writes to the database: recommending never locks a vehicle (NFR-S6)."""
    key = lambda v: (v.eta_s, v.distance_m, v.vehicle_id)         # deterministic tie-break
    out = Allocation(victims_unknown=need.victims_unknown)
    used: set[int] = set()
    for vtype, n in need.counts.items():
        pool = sorted((v for v in available if v.vehicle_type == vtype), key=key)
        out.chosen += pool[:n]
        used.update(v.vehicle_id for v in pool[:n])
        if len(pool) < n:
            out.shortage[vtype] = len(pool)
    rest = sorted((v for v in available if v.vehicle_id not in used and v.vehicle_type in need.counts), key=key)
    out.spare = rest[:spare_count]
    return out
