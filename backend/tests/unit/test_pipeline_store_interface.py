"""Contract C-6 tests (B1-A1-05): the pipeline persistence interface (signatures and row types only)."""
import inspect
from typing import Any, get_type_hints

import pytest
from pydantic import ValidationError

from app.schemas.ai import AllocationResult, DuplicateCandidateResult, GeocodeResult, TriageResult, TrustAssessment
from app.schemas.enums import PipelineState, VehicleType
from app.schemas.events import PipelineStage
from app.services import pipeline_store as ps
from app.services.pipeline_store import (
    CLAIMABLE_JOB_TYPES,
    CallerHistory,
    CandidateRow,
    PipelineJob,
    PipelineStore,
    VehicleRow,
)

# method -> (parameter names after self, annotated types of those parameters, return type)
EXPECTED: dict[str, tuple[list[str], list[Any], Any]] = {
    "claim_next": (["job_types"], [frozenset[PipelineState]], PipelineJob | None),
    "save_transcript": (["incident_id", "transcript", "transcript_unclear"], [int, str, bool], None),
    "save_location": (["incident_id", "result"], [int, GeocodeResult], None),
    "save_triage": (["incident_id", "result"], [int, TriageResult], None),
    "save_trust": (["incident_id", "assessment"], [int, TrustAssessment], None),
    "find_duplicate_candidates": (["incident_id", "distance_m", "window_min"], [int, int, int], list[CandidateRow]),
    "count_independent_nearby": (["incident_id", "distance_m", "window_min"], [int, int, int], int),
    "get_caller_history": (["caller_id"], [int], CallerHistory | None),
    "save_duplicate_results": (["incident_id", "results"], [int, list[DuplicateCandidateResult]], None),
    "list_available_vehicles": (["types"], [frozenset[VehicleType]], list[VehicleRow]),
    "save_recommendations": (["incident_id", "result"], [int, AllocationResult], None),
    "mark_stage_failed": (["incident_id", "stage", "error"], [int, PipelineStage, str], None),
    "mark_done": (["incident_id"], [int], None),
    "heartbeat": (["worker_id", "info"], [str, dict[str, Any]], None),
}


def protocol_methods() -> set[str]:
    return {n for n, v in vars(PipelineStore).items() if inspect.iscoroutinefunction(v)}


def test_interface_has_exactly_the_contracted_methods() -> None:
    assert protocol_methods() == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_method_signature(name: str) -> None:
    method = getattr(PipelineStore, name)
    assert inspect.iscoroutinefunction(method), "every method is async"
    params = list(inspect.signature(method).parameters)[1:]
    names, types, returns = EXPECTED[name]
    assert params == names
    hints = get_type_hints(method)
    assert [hints[p] for p in names] == types
    assert hints["return"] == (type(None) if returns is None else returns)


def test_claim_defaults_to_the_claimable_job_types() -> None:
    default = inspect.signature(PipelineStore.claim_next).parameters["job_types"].default
    assert default == CLAIMABLE_JOB_TYPES == {PipelineState.PENDING, PipelineState.REALLOCATE}


def _complete_store() -> type:
    async def method(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    return type("Complete", (), {name: method for name in EXPECTED})


def test_a_class_with_every_method_satisfies_the_protocol() -> None:
    assert isinstance(_complete_store()(), PipelineStore)


def test_a_class_missing_a_method_does_not() -> None:
    cls = _complete_store()
    delattr(cls, "mark_done")
    assert not isinstance(cls(), PipelineStore)


def test_module_states_the_safety_rules() -> None:
    doc = ps.__doc__ or ""
    assert "never locks a vehicle" in doc and "FOR UPDATE SKIP LOCKED" in doc and "NOTIFY incident_events" in doc


# ---------------------------------------------------------------- row types
JOB = {
    "incident_id": 1, "job_type": "pending", "attempts": 1, "channel": "web", "received_at": "2026-01-01T09:15:30Z",
    "original_text": "SIMULATED report", "audio_ref": None, "location_text": "near the market",
    "caller_gps": {"lat": 27.7, "lon": 68.85}, "caller_id": 4, "settings_snapshot": {"dup_auto_link": 85},
}


def test_pipeline_job_valid() -> None:
    job = PipelineJob.model_validate(JOB)
    assert job.job_type is PipelineState.PENDING
    with pytest.raises(ValidationError):
        job.attempts = 2  # rows are read-only


@pytest.mark.parametrize("bad", [
    {"job_type": "processing"}, {"job_type": "retrust"}, {"attempts": 0},
    {"received_at": "2026-01-01T09:15:30"}, {"channel": "mobile"}, {"extra": 1},
])
def test_pipeline_job_invalid(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PipelineJob.model_validate({**JOB, **bad})


def test_other_rows() -> None:
    CandidateRow(incident_id=2, incident_type="fire", received_at="2026-01-01T09:00:00Z", lat=27.7, lon=68.8,
                 original_text=None, caller_id=None)
    CallerHistory(caller_id=4, real_count=2, fake_count=0, flagged_until=None)
    VehicleRow(vehicle_id=5, vehicle_type="ambulance", lat=27.7, lon=68.8, patient_capacity=2, station_name=None)
    for model, data in [
        (CallerHistory, {"caller_id": 4, "real_count": -1, "fake_count": 0, "flagged_until": None}),
        (VehicleRow, {"vehicle_id": 5, "vehicle_type": "truck", "lat": 0, "lon": 0, "patient_capacity": 2,
                      "station_name": None}),
        (CandidateRow, {"incident_id": 2, "incident_type": None, "received_at": "2026-01-01T09:00:00Z",
                        "lat": 0, "lon": 0, "original_text": None, "caller_id": None}),
    ]:
        with pytest.raises(ValidationError):
            model.model_validate(data)
