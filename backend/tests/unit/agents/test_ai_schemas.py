"""Contract C-2 tests (B1-A2-01): AI input/output schemas.

Examples live in tests/fixtures/contracts/ai/examples (SIMULATED). The exported JSON Schemas live in
tests/fixtures/contracts/ai/schemas and must match the models; regenerate them with
UPDATE_CONTRACT_SCHEMAS=1 (see the README in that folder).
"""
import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import ai
from app.schemas.ai import (
    AGENT_DUPLICATE_DECISIONS,
    C2_MODELS,
    AllocationResult,
    DuplicateCandidateResult,
    GeocodeResult,
    GeocodeSource,
    RoutingMode,
    TriageInput,
    TriageResult,
    TrustAction,
    TrustAssessment,
    VehicleRecommendation,
)
from app.schemas.enums import DuplicateDecision

AI_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts" / "ai"
EXAMPLES = AI_FIXTURES / "examples"
SCHEMAS = AI_FIXTURES / "schemas"


def example(model: type[BaseModel]) -> dict[str, Any]:
    return json.loads((EXAMPLES / f"{model.__name__}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- examples and exported schemas
@pytest.mark.parametrize("model", C2_MODELS, ids=lambda m: m.__name__)
def test_example_validates_and_round_trips(model: type[BaseModel]) -> None:
    raw = example(model)
    assert model.model_validate(raw).model_dump(mode="json") == raw


@pytest.mark.parametrize("model", C2_MODELS, ids=lambda m: m.__name__)
def test_exported_json_schema_is_up_to_date(model: type[BaseModel]) -> None:
    path = SCHEMAS / f"{model.__name__}.schema.json"
    current = model.model_json_schema()
    if os.environ.get("UPDATE_CONTRACT_SCHEMAS") == "1":
        SCHEMAS.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert path.exists(), f"missing {path.name}; regenerate with UPDATE_CONTRACT_SCHEMAS=1"
    assert json.loads(path.read_text(encoding="utf-8")) == current, f"{path.name} is out of date"


def test_every_c2_model_is_listed() -> None:
    defined = {
        obj for obj in vars(ai).values()
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == ai.__name__
        and not obj.__name__.startswith("_")
    }
    nested_only = {ai.GeoPoint, ai.TrustSignal}
    assert defined - nested_only == set(C2_MODELS)


@pytest.mark.parametrize("model", C2_MODELS, ids=lambda m: m.__name__)
def test_unknown_fields_are_rejected(model: type[BaseModel]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({**example(model), "made_up_field": 1})


def test_examples_are_labelled_simulated() -> None:
    assert "SIMULATED" in example(TriageInput)["text"]
    assert "SIMULATED" in (AI_FIXTURES / "README.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- C-2 vocabularies
def test_c2_vocabularies() -> None:
    assert [m.value for m in GeocodeSource] == ["gazetteer", "nominatim", "gps", "unknown"]
    assert [m.value for m in TrustAction] == [
        "continue", "continue_and_confirm", "review_queue", "urgent_with_warning",
    ]
    assert [m.value for m in RoutingMode] == ["osrm", "straight_line"]
    assert AGENT_DUPLICATE_DECISIONS == {
        DuplicateDecision.AUTO_LINKED, DuplicateDecision.POSSIBLE, DuplicateDecision.SEPARATE,
    }


# ---------------------------------------------------------------- Triage
TRIAGE_CONFIDENCES = [
    "language_confidence", "type_confidence", "severity_confidence", "victims_confidence", "overall_confidence",
]


@pytest.mark.parametrize("field", TRIAGE_CONFIDENCES)
@pytest.mark.parametrize("value", [-0.01, 1.01, 88])
def test_triage_confidences_must_be_0_to_1(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        TriageResult.model_validate({**example(TriageResult), field: value})


def test_triage_unknowns_are_explicit_none() -> None:
    raw = example(TriageResult)
    for key in ("language", "language_confidence", "incident_type", "type_confidence", "severity",
                "severity_confidence", "victims_estimate", "victims_confidence", "location_words"):
        raw[key] = None
    result = TriageResult.model_validate(raw)
    assert result.location_words is None and result.incident_type is None


@pytest.mark.parametrize("key", ["incident_type", "location_words", "has_real_details", "overall_confidence", "model"])
def test_triage_every_key_must_be_present(key: str) -> None:
    raw = example(TriageResult)
    del raw[key]
    with pytest.raises(ValidationError):
        TriageResult.model_validate(raw)


def test_overall_confidence_cannot_be_unknown() -> None:
    with pytest.raises(ValidationError):
        TriageResult.model_validate({**example(TriageResult), "overall_confidence": None})


@pytest.mark.parametrize("field,value", [
    ("incident_type", "flood"), ("severity", "urgent"), ("victims_estimate", -1),
    ("location_words", ""), ("latency_ms", -5), ("prompt_version", ""),
])
def test_triage_invalid_values_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        TriageResult.model_validate({**example(TriageResult), field: value})


def test_triage_input_needs_text_and_valid_channel() -> None:
    for bad in ({"text": ""}, {"channel": "mobile"}, {"caller_gps": {"lat": 91, "lon": 0}}):
        with pytest.raises(ValidationError):
            TriageInput.model_validate({**example(TriageInput), **bad})


# ---------------------------------------------------------------- Geocoding
def test_geocode_unknown_has_no_coordinates() -> None:
    assert GeocodeResult(lat=None, lon=None, source="unknown", matched_name=None).lat is None


@pytest.mark.parametrize("kwargs", [
    {"lat": None, "lon": None, "source": "gazetteer", "matched_name": "x"},
    {"lat": None, "lon": None, "source": "gps", "matched_name": None},
    {"lat": 27.0, "lon": 68.0, "source": "unknown", "matched_name": None},
    {"lat": 27.0, "lon": None, "source": "nominatim", "matched_name": "x"},
    {"lat": 27.0, "lon": 68.0, "source": "gps", "matched_name": None, "distance_to_gps_m": -1},
])
def test_geocode_invalid_combinations_rejected(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GeocodeResult(**kwargs)


# ---------------------------------------------------------------- Trust
@pytest.mark.parametrize("score", [-1, 101])
def test_trust_score_bounds(score: int) -> None:
    with pytest.raises(ValidationError):
        TrustAssessment.model_validate({**example(TrustAssessment), "score": score})


def test_trust_signal_needs_a_reason() -> None:
    raw = example(TrustAssessment)
    raw["signals"][0]["detail"] = ""
    with pytest.raises(ValidationError):
        TrustAssessment.model_validate(raw)
    del raw["signals"][0]["detail"]
    with pytest.raises(ValidationError):
        TrustAssessment.model_validate(raw)


@pytest.mark.parametrize("field,value", [("tier", "very_high"), ("action", "dispatch")])
def test_trust_vocabulary_enforced(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TrustAssessment.model_validate({**example(TrustAssessment), field: value})


def test_c2_trust_signal_is_accepted_by_c1_read_schema() -> None:
    """A signal stored from C-2 must be readable through C-1 TrustSignalOut (v1.1)."""
    from app.schemas.incident import TrustSignalOut

    for signal in example(TrustAssessment)["signals"]:
        assert TrustSignalOut.model_validate(signal).detail == signal["detail"]


# ---------------------------------------------------------------- Coordination
@pytest.mark.parametrize("decision", ["auto_linked", "possible", "separate"])
def test_agent_duplicate_decisions_allowed(decision: str) -> None:
    assert DuplicateCandidateResult.model_validate({**example(DuplicateCandidateResult), "decision": decision})


def test_exported_schema_lists_only_agent_decisions() -> None:
    props = DuplicateCandidateResult.model_json_schema()["properties"]["decision"]
    assert props["enum"] == ["auto_linked", "possible", "separate"]


def test_agent_decision_is_the_c1_enum_member() -> None:
    result = DuplicateCandidateResult.model_validate(example(DuplicateCandidateResult))
    assert result.decision is DuplicateDecision.POSSIBLE


@pytest.mark.parametrize("decision", ["confirmed", "rejected", "auto_link", "maybe"])
def test_agent_cannot_confirm_reject_or_invent_decisions(decision: str) -> None:
    with pytest.raises(ValidationError):
        DuplicateCandidateResult.model_validate({**example(DuplicateCandidateResult), "decision": decision})


@pytest.mark.parametrize("field,value", [
    ("s_dist", 1.1), ("s_time", -0.1), ("s_meaning", 2), ("match_confidence", 101),
    ("match_confidence", -1), ("distance_m", -1), ("time_diff_s", -1),
])
def test_duplicate_scores_bounded(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        DuplicateCandidateResult.model_validate({**example(DuplicateCandidateResult), field: value})


# ---------------------------------------------------------------- Allocation
@pytest.mark.parametrize("field,value", [
    ("rank", 0), ("eta_seconds", -1), ("eta_seconds", None), ("distance_meters", None), ("vehicle_type", "truck"),
])
def test_vehicle_recommendation_invalid_values(field: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        VehicleRecommendation.model_validate({**example(VehicleRecommendation), field: value})


def test_vehicle_recommendation_field_is_route_geometry_not_route_polyline() -> None:
    assert "route_geometry" in VehicleRecommendation.model_fields
    with pytest.raises(ValidationError):
        VehicleRecommendation.model_validate({**example(VehicleRecommendation), "route_polyline": "abc"})


def test_allocation_needed_and_shortage_use_vehicle_types() -> None:
    raw = example(AllocationResult)
    for bad in ({"needed": {"truck": 1}}, {"needed": {"ambulance": -1}}, {"shortage": {"helicopter": 0}}):
        with pytest.raises(ValidationError):
            AllocationResult.model_validate({**raw, **bad})


def test_straight_line_routing_marks_every_eta_approximate() -> None:
    raw = copy.deepcopy(example(AllocationResult))
    raw["routing_mode"] = "straight_line"
    with pytest.raises(ValidationError):
        AllocationResult.model_validate(raw)
    for rec in raw["recommendations"]:
        rec["eta_is_approximate"] = True
    assert AllocationResult.model_validate(raw).routing_mode is RoutingMode.STRAIGHT_LINE


def test_allocation_with_shortage_and_unknown_victims_is_valid() -> None:
    raw = {**example(AllocationResult), "victims_unknown_check": True, "shortage": {"fire_truck": 0}}
    assert AllocationResult.model_validate(raw).shortage == {"fire_truck": 0}
