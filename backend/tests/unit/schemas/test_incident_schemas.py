"""Contract C-1 tests: Incident Record schemas against the SRS Appendix B sample and the fixture."""
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.enums import Channel, IncidentStatus, LocationSource
from app.schemas.incident import (
    DuplicateCandidateOut,
    IncidentDetailOut,
    IncidentSummaryOut,
    LocationOut,
)
from app.schemas.report import ReportIn

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "contracts" / "incident_detail.json"

# SRS v1.1 §7.2 (Appendix B), copied verbatim. NOTE: it shows location source "GPS" in capitals
# and a `vehicles` list; decision D-005 fixes the source value as lowercase "gps", and `vehicles`
# is carried by `recommendations` + `assignments` in the detail schema.
SRS_APPENDIX_B_SAMPLE: dict[str, Any] = {
    "incident_id": 123,
    "reference_no": "INC-000123",
    "channel": "web",
    "received_at": "2026-01-01T09:15:30Z",
    "original_text": "Bus accident near the market, many people hurt",
    "language": "English",
    "location": {"lat": 27.7052, "lon": 68.8574, "source": "GPS"},
    "incident_type": "accident",
    "severity": "high",
    "victims_estimate": 6,
    "confidence": 0.88,
    "trust_score": 78,
    "trust_tier": "high",
    "group_id": None,
    "status": "triaged",
    "vehicles": [],
    "dispatcher_decision": None,
}


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _sample_as_c1() -> dict[str, Any]:
    """The SRS sample adapted exactly as documented above (D-005 casing; `vehicles` dropped)."""
    data = copy.deepcopy(SRS_APPENDIX_B_SAMPLE)
    data["location"]["source"] = data["location"]["source"].lower()
    assert data.pop("vehicles") == []
    return data


# ---------------------------------------------------------------- SRS sample and fixture
def test_srs_appendix_b_sample_validates_after_documented_adaptation() -> None:
    detail = IncidentDetailOut.model_validate(_sample_as_c1())
    assert detail.reference_no == "INC-000123"
    assert detail.channel is Channel.WEB
    assert detail.status is IncidentStatus.TRIAGED
    assert detail.location.source is LocationSource.GPS
    assert detail.recommendations == [] and detail.assignments == []


def test_srs_sample_is_also_a_valid_summary_without_detail_fields() -> None:
    data = _sample_as_c1()
    for key in ("original_text", "dispatcher_decision"):
        data.pop(key)
    assert IncidentSummaryOut.model_validate(data).incident_id == 123


def test_srs_sample_uppercase_gps_is_rejected_per_d005() -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "location": SRS_APPENDIX_B_SAMPLE["location"]})


def test_fixture_validates_and_round_trips_unchanged() -> None:
    raw = _fixture()
    detail = IncidentDetailOut.model_validate(raw)
    assert detail.model_dump(mode="json") == raw


def test_fixture_is_labelled_simulated() -> None:
    assert "SIMULATED" in _fixture()["original_text"]


def test_fixture_exercises_every_detail_section() -> None:
    detail = IncidentDetailOut.model_validate(_fixture())
    assert detail.trust_signals and detail.duplicate_candidates
    assert detail.recommendations and detail.assignments and detail.dispatcher_decision
    assert any(r.eta_is_approximate for r in detail.recommendations)


# ---------------------------------------------------------------- bounds and shape
NEW_REPORT: dict[str, Any] = {
    "incident_id": 1, "reference_no": "INC-000001", "channel": "sms",
    "received_at": "2026-01-01T00:00:00Z", "status": "new", "location": {"source": "unknown"},
}


def test_new_report_with_nothing_filled_by_the_ai_is_valid() -> None:
    card = IncidentSummaryOut.model_validate(NEW_REPORT)
    assert card.severity is None and card.confidence is None and card.review_reasons == []
    assert card.location.source is LocationSource.UNKNOWN and card.location.lat is None


@pytest.mark.parametrize("location", ["missing", None])
def test_location_is_required(location: Any) -> None:
    data = {k: v for k, v in NEW_REPORT.items() if k != "location"}
    if location is None:
        data["location"] = None
    with pytest.raises(ValidationError):
        IncidentSummaryOut.model_validate(data)


def test_summary_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        IncidentSummaryOut.model_validate({**NEW_REPORT, "made_up_field": 1})


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 88])
def test_confidence_must_be_between_0_and_1(confidence: float) -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "confidence": confidence})


@pytest.mark.parametrize("confidence", [0, 0.0, 1, 1.0, 0.6])
def test_confidence_edges_accepted(confidence: float) -> None:
    assert IncidentDetailOut.model_validate({**_sample_as_c1(), "confidence": confidence}).confidence == confidence


@pytest.mark.parametrize("score", [-1, 101])
def test_trust_score_must_be_0_to_100(score: int) -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "trust_score": score})


@pytest.mark.parametrize("ref", ["123", "inc-000123", "INC-12", "INC-ABCDEF", ""])
def test_reference_no_format_is_enforced(ref: str) -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "reference_no": ref})


@pytest.mark.parametrize("field,value", [
    ("channel", "mobile"), ("status", "on scene"), ("severity", "urgent"),
    ("incident_type", "flood"), ("trust_tier", "medium-high"),
])
def test_values_outside_the_vocabulary_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), field: value})


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "received_at": "2026-01-01T09:15:30"})


def test_unknown_fields_are_rejected_so_drift_is_caught() -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "made_up_field": 1})


def test_negative_victims_rejected() -> None:
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate({**_sample_as_c1(), "victims_estimate": -1})


# ---------------------------------------------------------------- location
def test_location_unknown_may_have_no_coordinates() -> None:
    loc = LocationOut(source=LocationSource.UNKNOWN)
    assert loc.lat is None and loc.lon is None


def test_location_text_before_geocoding_has_words_but_no_coordinates() -> None:
    loc = LocationOut(text="near Sukkur barrage", source=LocationSource.TEXT)
    assert loc.text and loc.lat is None


def test_location_text_after_geocoding_has_words_and_coordinates() -> None:
    loc = LocationOut(text="near Sukkur barrage", lat=27.69, lon=68.86, source=LocationSource.TEXT)
    assert loc.lat == 27.69


def test_location_gps_with_coordinates_is_valid() -> None:
    assert LocationOut(lat=27.7, lon=68.8, source=LocationSource.GPS).lon == 68.8


@pytest.mark.parametrize("kwargs", [
    {"lat": 27.0, "text": "market", "source": "text"},
    {"lon": 68.0, "text": "market", "source": "text"},
    {"source": "text"},
    {"text": "   ", "source": "text"},
    {"lat": 27.0, "lon": 68.0, "source": "text"},
    {"source": "gps"},
    {"text": "market", "source": "gps"},
    {"lat": 91, "lon": 0, "source": "gps"},
    {"lat": 0, "lon": 181, "source": "gps"},
])
def test_invalid_locations_are_rejected(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        LocationOut(**kwargs)


# ---------------------------------------------------------------- nested lists
def test_trust_signal_detail_is_optional_since_c1_v1_1() -> None:
    from app.schemas.incident import TrustSignalOut

    assert TrustSignalOut(code="x", points=5).detail is None  # v1 data stays valid
    assert TrustSignalOut(code="x", points=5, detail="reason").detail == "reason"


def test_duplicate_candidate_bounds() -> None:
    ok = {"duplicate_id": 1, "candidate_incident_id": 2, "match_confidence": 85, "decision": "auto_linked"}
    assert DuplicateCandidateOut.model_validate(ok).match_confidence == 85
    for bad in ({"match_confidence": 101}, {"match_confidence": -1}, {"similarity": 1.2}, {"decision": "maybe"}):
        with pytest.raises(ValidationError):
            DuplicateCandidateOut.model_validate({**ok, **bad})


@pytest.mark.parametrize("field", ["eta_seconds", "distance_meters"])
def test_recommendation_eta_and_distance_are_required(field: str) -> None:
    missing = _fixture()
    del missing["recommendations"][1][field]
    empty = _fixture()
    empty["recommendations"][1][field] = None
    negative = _fixture()
    negative["recommendations"][1][field] = -1
    for raw in (missing, empty, negative):
        with pytest.raises(ValidationError):
            IncidentDetailOut.model_validate(raw)


def test_approximate_eta_still_has_a_value() -> None:
    approx = [r for r in IncidentDetailOut.model_validate(_fixture()).recommendations if r.eta_is_approximate]
    assert approx and all(r.eta_seconds >= 0 for r in approx)


def test_recommendation_rank_starts_at_one() -> None:
    raw = _fixture()
    raw["recommendations"][0]["rank"] = 0
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate(raw)


def test_assignment_status_uses_the_d005_vocabulary() -> None:
    raw = _fixture()
    raw["assignments"][0]["status"] = "on_scene"  # a vehicle status, not an assignment status
    with pytest.raises(ValidationError):
        IncidentDetailOut.model_validate(raw)


# ---------------------------------------------------------------- report input (channel correction)
#: D-036: place, name and phone are required, so every valid ReportIn carries them (SIMULATED values)
REPORT_OK = {"description": "x", "address_text": "SIMULATED place", "reporter_name": "SIMULATED caller",
             "reporter_phone": "03001234567"}


def test_report_in_accepts_app_and_defaults_to_web() -> None:
    assert ReportIn(**REPORT_OK).channel is Channel.WEB
    assert ReportIn(**REPORT_OK, channel="app").channel is Channel.APP


@pytest.mark.parametrize("channel", ["voice", "sms"])
def test_public_report_form_refuses_voice_and_sms(channel: str) -> None:
    """Since B1-A1-16 the public text form takes web and app only; SMS and voice have their own endpoints."""
    with pytest.raises(ValidationError):
        ReportIn(**REPORT_OK, channel=channel)


def test_report_in_rejects_the_old_mobile_channel() -> None:
    with pytest.raises(ValidationError):
        ReportIn(**REPORT_OK, channel="mobile")
