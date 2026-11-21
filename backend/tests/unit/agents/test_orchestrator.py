"""Orchestrator tests (B1-A2-13): stage order, persistence per stage, retries, failure -> manual mode,
D-021, D-035, safety rules 3 and 7. Fake model + in-memory C-6 store; no network, no database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.agents.orchestrator import GpsOnlyGeocoder, Orchestrator
from app.agents.triage import TriageAgent
from app.llm.fake import FakeLLMClient
from app.llm.gateway import LLMError, LLMTimeout
from app.schemas.ai import GeocodeSource
from app.schemas.events import PipelineStage as S
from app.services.pipeline_store import CallerHistory, PipelineStore
from tests.unit.agents.fakes import FakeStore, ambulance, job, triage_reply

FLEET = [ambulance(1, 1), ambulance(2, 2), ambulance(3, 3), ambulance(4, 4), ambulance(5, 9, "fire_truck")]


def orch(replies, store: FakeStore | None = None, **kw) -> tuple[Orchestrator, FakeStore]:
    store = store or FakeStore(vehicles=FLEET)
    return Orchestrator(store, TriageAgent(FakeLLMClient(replies)), backoff_s=(0, 0), **kw), store


def test_fake_store_is_a_c6_store_and_the_graph_is_langgraph() -> None:
    o, store = orch([])
    assert isinstance(store, PipelineStore)
    assert type(o.graph).__name__ == "CompiledStateGraph"
    assert {"speech_to_text", "geocoding", "triage", "trust", "coordination", "allocation"} <= set(o.graph.get_graph().nodes)


# ---------------------------------------------------------------- happy path (text report)
async def test_text_report_runs_every_stage_in_order_and_saves_each() -> None:
    o, store = orch([triage_reply()])
    outcome = await o.run(job())
    saves = [n for n in store.names() if n.startswith(("save_", "mark_"))]
    assert saves == ["save_location", "save_triage", "save_trust", "save_recommendations", "mark_done"]
    assert outcome.done and outcome.ran == [S.GEOCODING, S.TRIAGE, S.TRUST, S.ALLOCATION]
    assert store.state[1] == "done" and set(outcome.timings_ms) == set(outcome.ran)


async def test_stages_that_are_not_built_are_reported_as_skipped_not_faked() -> None:
    o, store = orch([triage_reply()])
    outcome = await o.run(job())
    assert "B1-A2-08" in outcome.skipped[S.COORDINATION] and "B1-A2-05" in outcome.skipped[S.GEOCODING]
    assert "save_duplicate_results" not in store.names()


async def test_allocation_uses_triage_and_the_snapshot() -> None:
    o, store = orch([triage_reply(victims_estimate=3)])
    await o.run(job(patients_per_ambulance=3))
    result = store.saved["allocation"]
    assert result.needed == {"ambulance": 1} and result.routing_mode == "straight_line"
    assert [r.vehicle_id for r in result.recommendations] == [1, 2, 3]  # 1 needed + 2 spare, nearest first
    assert ("list_available_vehicles", frozenset({"ambulance"})) in store.calls


async def test_other_type_lists_every_vehicle_type_for_the_dispatcher() -> None:
    o, store = orch([triage_reply(incident_type="other")])
    await o.run(job())
    assert [t for n, t in store.calls if n == "list_available_vehicles"] == [frozenset({"ambulance", "fire_truck", "backup"})]


# ---------------------------------------------------------------- location
async def test_gps_becomes_the_location_without_a_trust_gps_signal() -> None:
    o, store = orch([triage_reply()])
    await o.run(job())
    loc = store.saved["location"]
    assert loc.source is GeocodeSource.GPS and loc.distance_to_gps_m is None
    assert not {s.code for s in store.saved["trust"].signals} & {"gps_match", "gps_far"}


async def test_no_gps_means_location_unknown_and_no_ranking_but_the_report_continues() -> None:
    o, store = orch([triage_reply()])
    outcome = await o.run(job(gps=None))
    assert store.saved["location"].source is GeocodeSource.UNKNOWN
    assert store.saved["allocation"].recommendations == [] and store.saved["allocation"].needed == {"ambulance": 2}
    assert outcome.done


async def test_a_broken_geocoder_never_loses_the_report() -> None:
    class Broken:
        async def locate(self, job):
            raise RuntimeError("SIMULATED geocoder down")

    o, store = orch([triage_reply()], geocoder=Broken())
    outcome = await o.run(job())
    assert store.saved["location"].source is GeocodeSource.UNKNOWN and outcome.done


# ---------------------------------------------------------------- failures -> manual mode (safety rule 7)
async def test_triage_failure_goes_to_manual_mode_and_trust_still_runs_d035() -> None:
    o, store = orch(["garbage", "garbage again"])
    outcome = await o.run(job())
    assert outcome.failed is S.TRIAGE and ("mark_stage_failed", S.TRIAGE) in store.calls
    assert "save_triage" not in store.names() and "save_recommendations" not in store.names()
    assert "mark_done" not in store.names() and store.state[1] == "failed"
    trust = store.saved["trust"]
    assert "ai_unavailable" in {s.code for s in trust.signals} and trust.action != "review_queue"


async def test_transient_errors_are_retried_with_backoff() -> None:
    o, store = orch([LLMTimeout(), LLMError("SIMULATED 503", transient=True), triage_reply()])
    outcome = await o.run(job())
    assert outcome.done and "save_triage" in store.names()


async def test_too_many_transient_errors_fail_the_stage() -> None:
    o, store = orch([LLMTimeout(), LLMTimeout(), LLMTimeout(), triage_reply()])
    outcome = await o.run(job())
    assert outcome.failed is S.TRIAGE and "language model unavailable" in store.saved["error"]


async def test_a_permanent_llm_error_is_not_retried_by_the_orchestrator() -> None:
    fake = FakeLLMClient([LLMError("SIMULATED 401"), LLMError("SIMULATED 401"), triage_reply()])
    store = FakeStore(vehicles=FLEET)
    outcome = await Orchestrator(store, TriageAgent(fake), backoff_s=(0,)).run(job())
    assert outcome.failed is S.TRIAGE and len(fake.calls) == 2  # Triage's own single retry only


async def test_allocation_crash_keeps_the_earlier_results() -> None:
    class Broken(FakeStore):
        async def list_available_vehicles(self, types):
            raise RuntimeError("SIMULATED")

    o, store = orch([triage_reply()], store=Broken())
    outcome = await o.run(job())
    assert outcome.failed is S.ALLOCATION and {"save_triage", "save_trust"} <= set(store.names())
    assert "mark_done" not in store.names()


async def test_voice_report_without_text_fails_speech_to_text_openly() -> None:
    o, store = orch([triage_reply()])
    outcome = await o.run(job(channel="voice", text=None))
    assert outcome.failed is S.SPEECH_TO_TEXT and "B1-A2-04" in store.saved["error"]
    assert "save_triage" not in store.names() and "save_trust" in store.names()  # D-035


# ---------------------------------------------------------------- D-021 and safety rule 3
def low_trust_store() -> FakeStore:
    return FakeStore(vehicles=FLEET, history={9: CallerHistory(caller_id=9, real_count=0, fake_count=2, flagged_until=None)})


async def test_low_trust_low_severity_waits_for_the_dispatcher() -> None:
    o, store = orch([triage_reply(severity="low")], store=low_trust_store())
    outcome = await o.run(job(caller_id=9))
    assert store.saved["trust"].action == "review_queue"
    assert "save_recommendations" not in store.names() and "D-021" in outcome.skipped[S.ALLOCATION]
    assert outcome.done  # the AI work is finished; the report waits in the review queue


@pytest.mark.parametrize("severity", ["high", "critical", None])
async def test_low_trust_urgent_or_unknown_still_gets_vehicles(severity) -> None:
    o, store = orch([triage_reply(severity=severity, severity_confidence=None)], store=low_trust_store())
    await o.run(job(caller_id=9))
    assert store.saved["trust"].tier == "low" and store.saved["trust"].action == "urgent_with_warning"
    assert store.saved["allocation"].recommendations


# ---------------------------------------------------------------- trust inputs
async def test_trust_uses_history_nearby_flood_and_triage() -> None:
    later = datetime.now(timezone.utc) + timedelta(minutes=5)
    store = FakeStore(vehicles=FLEET, nearby=2,
                      history={4: CallerHistory(caller_id=4, real_count=1, fake_count=0, flagged_until=later)})
    o, _ = orch([triage_reply()], store=store)
    await o.run(job(caller_id=4, dup_distance_m=500, dup_window_min=20))
    codes = {s.code for s in store.saved["trust"].signals}
    assert codes == {"real_history", "nearby_two_plus", "real_details", "flood"}
    assert ("count_independent_nearby", (500, 20)) in store.calls  # the incident's own snapshot


async def test_unknown_caller_is_neutral() -> None:
    o, store = orch([triage_reply(has_real_details=False)])
    await o.run(job(caller_id=None))
    assert store.saved["trust"].signals == [] and store.saved["trust"].score == 50
    assert "get_caller_history" not in store.names()


async def test_a_plugged_in_coordinator_runs_between_trust_and_allocation() -> None:
    seen = []

    class Coord:
        async def run(self, job, triage, store):
            seen.append(store.names()[-1])

    o, store = orch([triage_reply()], coordinator=Coord())
    outcome = await o.run(job())
    assert seen == ["save_trust"] and S.COORDINATION in outcome.ran


async def test_a_failing_coordinator_never_holds_the_report_back() -> None:
    class Coord:
        async def run(self, job, triage, store):
            raise RuntimeError("SIMULATED")

    o, store = orch([triage_reply(severity="critical")], coordinator=Coord())
    outcome = await o.run(job())
    assert outcome.done and "save_recommendations" in store.names()


def test_gps_only_geocoder_is_the_default() -> None:
    assert isinstance(orch([])[0].geocoder, GpsOnlyGeocoder)
