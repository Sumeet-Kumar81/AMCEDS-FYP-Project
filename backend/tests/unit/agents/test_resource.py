"""Resource Allocation Agent tests (B1-A2-11): SRS Table 7.3.3 + D-019, TC-16…TC-19, ranking, no locking."""
import pytest

from app.agents.resource import (
    AllocationInput,
    Eta,
    ResourceAllocationAgent,
    StraightLineEta,
    straight_line_m,
    vehicles_needed,
)
from app.schemas.ai import RoutingMode
from app.services.pipeline_store import VehicleRow

SCENE = (27.7052, 68.8574)
agent = ResourceAllocationAgent()


def vehicle(vid: int, vtype: str = "ambulance", km: float = 1.0) -> VehicleRow:
    """A SIMULATED vehicle `km` kilometres north of the scene (1° latitude ≈ 111.2 km)."""
    return VehicleRow(vehicle_id=vid, vehicle_type=vtype, lat=SCENE[0] + km / 111.2, lon=SCENE[1],
                      patient_capacity=2 if vtype == "ambulance" else 0, station_name=None)


def incident(kind: str | None = "accident", severity: str | None = "high", victims: int | None = 2,
             here: bool = True) -> AllocationInput:
    return AllocationInput(incident_type=kind, severity=severity, victims=victims,
                           lat=SCENE[0] if here else None, lon=SCENE[1] if here else None)


# ---------------------------------------------------------------- vehicles needed (Table 7.3.3 + D-019)
@pytest.mark.parametrize(("kind", "severity", "victims", "counts", "check"), [
    ("accident", "high", 6, {"ambulance": 3}, False),
    ("accident", "high", 5, {"ambulance": 3}, False),
    ("accident", "critical", 1, {"ambulance": 1, "backup": 1}, False),
    ("accident", "medium", 0, {"ambulance": 1}, True),  # D-019: no injuries → 1 ambulance + please check
    ("accident", "high", None, {"ambulance": 1}, True),  # victims unknown
    ("fire", "high", 4, {"fire_truck": 1, "ambulance": 2, "backup": 1}, False),
    ("fire", "low", None, {"fire_truck": 1, "ambulance": 1, "backup": 1}, True),  # 1 of each needed type
    ("medical", "medium", 1, {"ambulance": 1}, False),
    ("medical", "medium", 0, {"ambulance": 1}, False),
])
def test_vehicles_needed(kind, severity, victims, counts, check) -> None:
    need = vehicles_needed(kind, severity, victims, 2)
    assert {k.value: v for k, v in need.counts.items()} == counts and need.check_victims is check
    assert not need.dispatcher_chooses


@pytest.mark.parametrize("kind", ["other", None])
def test_other_or_unknown_type_means_the_dispatcher_chooses(kind) -> None:
    need = vehicles_needed(kind, "high", 3, 2)
    assert need.counts == {} and need.dispatcher_chooses


def test_patients_per_ambulance_comes_from_settings() -> None:
    assert vehicles_needed("medical", "high", 6, 3).counts == {"ambulance": 2}


# ---------------------------------------------------------------- SRS test cases
async def test_tc16_six_victims_three_ambulances_plus_two_spare() -> None:
    result = await agent.run(incident(victims=6), [vehicle(i, km=i) for i in range(1, 8)])
    assert [r.vehicle_id for r in result.recommendations] == [1, 2, 3, 4, 5]
    assert [r.is_spare for r in result.recommendations] == [False, False, False, True, True]
    assert [r.rank for r in result.recommendations] == [1, 2, 3, 4, 5]
    assert result.shortage is None and result.needed == {"ambulance": 3}


async def test_tc17_unknown_victims_one_vehicle_and_check() -> None:
    result = await agent.run(incident(victims=None), [vehicle(i, km=i) for i in range(1, 5)])
    assert result.victims_unknown_check and sum(not r.is_spare for r in result.recommendations) == 1


async def test_tc18_fire_gets_truck_ambulances_and_backup() -> None:
    fleet = [vehicle(1, "fire_truck", 2), vehicle(2, "ambulance", 1), vehicle(3, "ambulance", 3),
             vehicle(4, "backup", 4), vehicle(5, "fire_truck", 5), vehicle(6, "ambulance", 6)]
    result = await agent.run(incident("fire", victims=3), fleet)
    needed = [(r.vehicle_id, r.vehicle_type) for r in result.recommendations if not r.is_spare]
    assert sorted(t for _, t in needed) == ["ambulance", "ambulance", "backup", "fire_truck"]
    assert sum(r.is_spare for r in result.recommendations) == 2  # D-019: 2 spare in total, not per type


async def test_tc19_shortage_reports_how_many_are_free() -> None:
    result = await agent.run(incident(victims=6), [vehicle(1), vehicle(2)])
    assert result.shortage == {"ambulance": 2} and len(result.recommendations) == 2
    assert not any(r.is_spare for r in result.recommendations)


async def test_missing_type_is_a_shortage_of_zero() -> None:
    result = await agent.run(incident("fire", victims=1), [vehicle(1, "ambulance")])
    assert result.shortage == {"fire_truck": 0, "backup": 0}


# ---------------------------------------------------------------- ranking and other rules
async def test_ranking_is_by_eta_then_distance_then_id() -> None:
    result = await agent.run(incident(victims=2), [vehicle(9, km=3), vehicle(4, km=1), vehicle(2, km=1), vehicle(7, km=2)])
    assert [r.vehicle_id for r in result.recommendations] == [2, 4, 7]


async def test_dispatcher_chooses_lists_every_available_vehicle_nearest_first() -> None:
    fleet = [vehicle(1, "backup", 5), vehicle(2, "fire_truck", 1), vehicle(3, "ambulance", 3)]
    result = await agent.run(incident("other"), fleet)
    assert [r.vehicle_id for r in result.recommendations] == [2, 3, 1] and result.needed == {}


async def test_types_that_are_not_needed_are_not_listed() -> None:
    result = await agent.run(incident("medical", victims=1), [vehicle(1, "fire_truck", 1), vehicle(2, "ambulance", 9)])
    assert [r.vehicle_id for r in result.recommendations] == [2]


async def test_no_location_means_no_ranking_but_the_need_is_known() -> None:
    result = await agent.run(incident(victims=4, here=False), [vehicle(1)])
    assert result.recommendations == [] and result.needed == {"ambulance": 2}


# ---------------------------------------------------------------- straight-line fallback (safety rule 7)
async def test_straight_line_etas_are_marked_approximate() -> None:
    result = await agent.run(incident(victims=1), [vehicle(1, km=10)])
    rec = result.recommendations[0]
    assert result.routing_mode is RoutingMode.STRAIGHT_LINE and rec.eta_is_approximate
    assert abs(rec.distance_meters - 10_000) < 50 and abs(rec.eta_seconds - 900) <= 5  # 10 km at 40 km/h


async def test_fallback_speed_comes_from_settings() -> None:
    result = await agent.run(incident(victims=1), [vehicle(1, km=10)], {"fallback_speed_kmh": 20})
    assert abs(result.recommendations[0].eta_seconds - 1800) <= 5


def test_haversine_distance() -> None:
    assert abs(straight_line_m(27.0, 68.0, 28.0, 68.0) - 111_195) < 10


def test_speed_must_be_positive() -> None:
    with pytest.raises(ValueError):
        StraightLineEta(0)


async def test_a_routing_provider_plugs_in_without_changing_the_agent() -> None:
    class FakeRouter:  # stands in for the OSRM provider of B1-A2-10
        mode = RoutingMode.OSRM

        async def eta(self, *coords) -> Eta:
            return Eta(seconds=123, meters=456, approximate=False)

    result = await ResourceAllocationAgent(FakeRouter()).run(incident(victims=1), [vehicle(1)])
    assert result.routing_mode is RoutingMode.OSRM and result.recommendations[0].eta_seconds == 123


# ---------------------------------------------------------------- never writes, never locks (safety rule 6)
async def test_the_agent_only_reads_its_input() -> None:
    fleet = (vehicle(1), vehicle(2))  # frozen rows in a tuple: any attempt to change them would raise
    result = await agent.run(incident(victims=2), list(fleet))
    assert len(result.recommendations) == 2 and fleet == (vehicle(1), vehicle(2))


def test_the_agent_has_no_database_access() -> None:
    import app.agents.resource as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "AsyncSession" not in source and "session" not in source.lower().replace("_sessions", "")
