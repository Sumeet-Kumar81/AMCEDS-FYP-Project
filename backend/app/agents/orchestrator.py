"""Agent orchestrator (SDS §3.1 steps 7–14, §4.2, Table 6.3 AgentOrchestrator). Task B1-A2-13.

A LangGraph ``StateGraph`` runs the stages of one claimed report in order:

    speech_to_text (voice only) -> geocoding -> triage -> trust -> coordination -> allocation -> done

* Every stage writes its result through the C-6 ``PipelineStore`` before the next one starts, so a
  later failure cannot erase an earlier result. The original report is never changed.
* Transient errors (LLM timeout, connection, HTTP 429/5xx) are retried up to ``retries`` times with
  backoff. A permanent Triage failure -> ``mark_stage_failed``: the report gets ``ai_failed``, goes to
  ``needs_check`` and the dispatcher continues by hand (safety rule 7).
* D-035: when Triage (or speech-to-text) fails, the Trust Scorer still runs on its non-LLM signals and
  shows "AI unavailable"; the report is never marked fake because of the failure. Coordination and
  allocation do not run on a failed report (no type to compare or allocate for); the dispatcher
  dispatches manually.
* D-021: a ``review_queue`` report (low trust, low/medium severity) gets no recommendation until the
  dispatcher marks it Real. High, critical and unknown severity always get vehicles (safety rule 3).
* The orchestrator never dispatches, never locks a vehicle and never sets ``dispatched``.

Stages that are not built yet are skipped openly, never faked (reported in ``PipelineOutcome.skipped``
and in the log):
  * speech-to-text (B1-A2-04): a voice report without text fails the ``speech_to_text`` stage -> manual.
  * geocoding (B1-A2-05, needs D-009): ``GpsOnlyGeocoder`` uses the caller's GPS as the location;
    without GPS the location is ``unknown`` and the dispatcher places it on the map.
  * coordination (B1-A2-08/09): skipped until a Coordination Agent is passed in.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.policy import allocate_now
from app.agents.resource import AllocationInput, ResourceAllocationAgent, vehicles_needed
from app.agents.triage import TriageAgent, TriageFailed
from app.agents.trust import TrustInputs, TrustScorer
from app.llm.gateway import LLMError
from app.schemas.ai import GeocodeResult, GeocodeSource, TriageInput, TriageResult, TrustAssessment
from app.schemas.enums import Channel, VehicleType
from app.schemas.events import PipelineStage
from app.services.pipeline_store import PipelineJob, PipelineStore
from app.services.settings import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ pluggable stages
class Geocoder(Protocol):
    async def locate(self, job: PipelineJob) -> GeocodeResult: ...


class GpsOnlyGeocoder:
    """Until the gazetteer/Nominatim geocoder exists (B1-A2-05): the caller's GPS is the incident location.
    ``distance_to_gps_m`` stays ``None`` (there is no separate place to compare with), so the trust
    GPS signals neither add nor take points."""

    name = "gps_only"

    async def locate(self, job: PipelineJob) -> GeocodeResult:
        if job.caller_gps is None:
            return GeocodeResult(lat=None, lon=None, source=GeocodeSource.UNKNOWN, matched_name=None)
        return GeocodeResult(lat=job.caller_gps.lat, lon=job.caller_gps.lon, source=GeocodeSource.GPS, matched_name=None)


class Coordinator(Protocol):
    async def run(self, job: PipelineJob, triage: TriageResult, store: PipelineStore) -> None: ...


# ------------------------------------------------------------------ state and outcome
class _State(TypedDict, total=False):
    job: PipelineJob
    geocode: GeocodeResult
    triage: TriageResult | None
    trust: TrustAssessment
    failed: PipelineStage | None


@dataclass
class PipelineOutcome:
    incident_id: int
    ran: list[PipelineStage] = field(default_factory=list)
    skipped: dict[PipelineStage, str] = field(default_factory=dict)
    failed: PipelineStage | None = None
    timings_ms: dict[PipelineStage, int] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.failed is None


def _setting(job: PipelineJob, key: str) -> Any:
    return job.settings_snapshot.get(key, REGISTRY[key].default)


class Orchestrator:
    def __init__(self, store: PipelineStore, triage: TriageAgent, *, trust: TrustScorer | None = None,
                 allocation: ResourceAllocationAgent | None = None, geocoder: Geocoder | None = None,
                 coordinator: Coordinator | None = None, retries: int = 2,
                 backoff_s: Sequence[float] = (0.5, 1.5)) -> None:
        self.store = store
        self.triage = triage
        self.trust = trust or TrustScorer()
        self.allocation = allocation or ResourceAllocationAgent()
        self.geocoder = geocoder or GpsOnlyGeocoder()
        self.coordinator = coordinator
        self.retries = retries
        self.backoff_s = tuple(backoff_s)
        self.graph = self._build()

    # -------------------------------------------------------------- graph
    def _build(self):
        g = StateGraph(_State)
        g.add_node("speech_to_text", self._speech_to_text)
        g.add_node("geocoding", self._geocoding)
        g.add_node("triage", self._triage)
        g.add_node("trust", self._trust)
        g.add_node("coordination", self._coordination)
        g.add_node("allocation", self._allocation)
        g.add_node("finish", self._finish)
        g.add_conditional_edges(START, lambda s: "speech_to_text" if self._needs_stt(s["job"]) else "geocoding",
                                ["speech_to_text", "geocoding"])
        g.add_edge("speech_to_text", "geocoding")
        g.add_edge("geocoding", "triage")
        g.add_edge("triage", "trust")
        g.add_conditional_edges("trust", lambda s: END if s.get("failed") else "coordination", ["coordination", END])
        g.add_edge("coordination", "allocation")
        g.add_edge("allocation", "finish")
        g.add_edge("finish", END)
        return g.compile()

    @staticmethod
    def _needs_stt(job: PipelineJob) -> bool:
        return job.channel is Channel.VOICE and not job.original_text

    async def run(self, job: PipelineJob) -> PipelineOutcome:
        outcome = PipelineOutcome(job.incident_id)  # passed to the nodes through the run config: safe to run jobs in parallel
        await self.graph.ainvoke({"job": job, "triage": None, "failed": None}, {"configurable": {"outcome": outcome}})
        logger.info("incident %s: pipeline %s; ran=%s skipped=%s timings_ms=%s", job.incident_id,
                    "done" if outcome.done else f"failed at {outcome.failed}", [s.value for s in outcome.ran],
                    {k.value: v for k, v in outcome.skipped.items()}, {k.value: v for k, v in outcome.timings_ms.items()})
        return outcome

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _out(config: RunnableConfig) -> PipelineOutcome:
        return config["configurable"]["outcome"]

    async def _fail(self, out: PipelineOutcome, job: PipelineJob, stage: PipelineStage, error: str) -> dict:
        await self.store.mark_stage_failed(job.incident_id, stage, error)
        out.failed = stage
        return {"failed": stage}

    def _timed(self, out: PipelineOutcome, stage: PipelineStage, started: float) -> None:
        out.timings_ms[stage] = round((time.perf_counter() - started) * 1000)

    # -------------------------------------------------------------- nodes
    async def _speech_to_text(self, state: _State, config: RunnableConfig) -> dict:
        out = self._out(config)
        return await self._fail(out, state["job"], PipelineStage.SPEECH_TO_TEXT,
                                "speech-to-text is not available yet (B1-A2-04); listen to the recording")

    async def _geocoding(self, state: _State, config: RunnableConfig) -> dict:
        out, job, started = self._out(config), state["job"], time.perf_counter()
        try:
            result = await self.geocoder.locate(job)
        except Exception as exc:  # a geocoder problem must not lose the report: the location is just unknown
            logger.warning("incident %s: geocoder failed (%s); location unknown", job.incident_id, exc.__class__.__name__)
            result = GeocodeResult(lat=None, lon=None, source=GeocodeSource.UNKNOWN, matched_name=None)
        await self.store.save_location(job.incident_id, result)
        if isinstance(self.geocoder, GpsOnlyGeocoder):
            out.skipped.setdefault(PipelineStage.GEOCODING, "place names not geocoded yet (B1-A2-05); caller GPS used")
        out.ran.append(PipelineStage.GEOCODING)
        self._timed(out, PipelineStage.GEOCODING, started)
        return {"geocode": result}

    async def _triage(self, state: _State, config: RunnableConfig) -> dict:
        out, job = self._out(config), state["job"]
        if state.get("failed"):  # speech-to-text failed: no text to read
            return {"triage": None}
        started = time.perf_counter()
        inp = TriageInput(incident_id=job.incident_id, text=job.original_text or "", channel=job.channel,
                          caller_gps=job.caller_gps, location_text=job.location_text)
        attempt = 0
        while True:
            try:
                result = await self.triage.run(inp)
                break
            except TriageFailed as exc:
                return {**await self._fail(out, job, PipelineStage.TRIAGE, str(exc)), "triage": None}
            except LLMError as exc:
                if not exc.transient or attempt >= self.retries:
                    return {**await self._fail(out, job, PipelineStage.TRIAGE, f"language model unavailable: {exc}"),
                            "triage": None}
                delay = self.backoff_s[min(attempt, len(self.backoff_s) - 1)] if self.backoff_s else 0
                attempt += 1
                logger.info("incident %s: triage attempt %s failed (%s); retrying in %.1fs",
                            job.incident_id, attempt, exc, delay)
                await asyncio.sleep(delay)
        await self.store.save_triage(job.incident_id, result)
        out.ran.append(PipelineStage.TRIAGE)
        self._timed(out, PipelineStage.TRIAGE, started)
        return {"triage": result}

    async def _trust(self, state: _State, config: RunnableConfig) -> dict:
        out, job, started = self._out(config), state["job"], time.perf_counter()
        triage, geocode = state.get("triage"), state.get("geocode")
        try:
            history = await self.store.get_caller_history(job.caller_id) if job.caller_id is not None else None
            nearby = 0
            if triage is not None:  # nearby reports are matched by type, which only Triage knows
                nearby = await self.store.count_independent_nearby(
                    job.incident_id, int(_setting(job, "dup_distance_m")), int(_setting(job, "dup_window_min")))
            flood = bool(history and history.flagged_until and history.flagged_until > datetime.now(timezone.utc))
            inputs = TrustInputs(
                real_count=history.real_count if history else 0, fake_count=history.fake_count if history else 0,
                distance_to_gps_m=geocode.distance_to_gps_m if geocode else None, independent_nearby=nearby,
                has_real_details=triage.has_real_details if triage else None,
                vague_or_joking=triage.vague_or_joking if triage else None, device_flood=flood)
            assessment = self.trust.assess(inputs, triage.severity if triage else None, job.settings_snapshot)
            await self.store.save_trust(job.incident_id, assessment)
        except Exception as exc:
            logger.exception("incident %s: trust stage failed", job.incident_id)
            if state.get("failed"):
                return {}
            return await self._fail(out, job, PipelineStage.TRUST, f"{exc.__class__.__name__}: {exc}"[:300])
        out.ran.append(PipelineStage.TRUST)
        self._timed(out, PipelineStage.TRUST, started)
        return {"trust": assessment}

    async def _coordination(self, state: _State, config: RunnableConfig) -> dict:
        out, job = self._out(config), state["job"]
        if self.coordinator is None:
            out.skipped[PipelineStage.COORDINATION] = "duplicate detection not built yet (B1-A2-08/09)"
            return {}
        started = time.perf_counter()
        try:
            await self.coordinator.run(job, state["triage"], self.store)
        except Exception as exc:  # a duplicate check problem never holds a report back (safety rule 3)
            logger.warning("incident %s: coordination failed (%s); reports stay separate", job.incident_id, exc)
            out.skipped[PipelineStage.COORDINATION] = f"failed: {exc.__class__.__name__}"
            return {}
        out.ran.append(PipelineStage.COORDINATION)
        self._timed(out, PipelineStage.COORDINATION, started)
        return {}

    async def _allocation(self, state: _State, config: RunnableConfig) -> dict:
        out, job, triage, geocode = self._out(config), state["job"], state["triage"], state["geocode"]
        if not allocate_now(state["trust"].action):
            out.skipped[PipelineStage.ALLOCATION] = "low trust, low/medium severity: waits for the dispatcher (D-021)"
            return {}
        started = time.perf_counter()
        try:
            per_amb = int(_setting(job, "patients_per_ambulance"))
            need = vehicles_needed(triage.incident_type, triage.severity, triage.victims_estimate, per_amb)
            types = frozenset(VehicleType) if need.dispatcher_chooses else frozenset(need.counts)
            vehicles = await self.store.list_available_vehicles(types)
            result = await self.allocation.run(
                AllocationInput(incident_type=triage.incident_type, severity=triage.severity,
                                victims=triage.victims_estimate, lat=geocode.lat, lon=geocode.lon),
                vehicles, job.settings_snapshot)
            await self.store.save_recommendations(job.incident_id, result)
        except Exception as exc:
            logger.exception("incident %s: allocation failed", job.incident_id)
            return await self._fail(out, job, PipelineStage.ALLOCATION, f"{exc.__class__.__name__}: {exc}"[:300])
        out.ran.append(PipelineStage.ALLOCATION)
        self._timed(out, PipelineStage.ALLOCATION, started)
        return {}

    async def _finish(self, state: _State, config: RunnableConfig) -> dict:
        if not state.get("failed"):
            await self.store.mark_done(state["job"].incident_id)
        return {}
