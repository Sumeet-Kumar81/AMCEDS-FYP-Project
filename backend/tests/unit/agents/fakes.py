"""In-memory C-6 store and helpers for the orchestrator and worker tests (SIMULATED data only)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.schemas.ai import GeoPoint
from app.schemas.enums import PipelineState
from app.services.pipeline_store import CallerHistory, PipelineJob, VehicleRow
from app.services.settings import defaults

SCENE = (27.7052, 68.8574)  # SIMULATED point in Sukkur


def job(incident_id: int = 1, *, text: str | None = "SIMULATED: bus accident near Clock Tower, 3 hurt",
        channel: str = "web", gps: tuple[float, float] | None = SCENE, caller_id: int | None = None,
        location_text: str | None = None, **snapshot: Any) -> PipelineJob:
    return PipelineJob(incident_id=incident_id, job_type="pending", attempts=1, channel=channel,
                       received_at=datetime.now(timezone.utc), original_text=text,
                       audio_ref="SIMULATED.ogg" if channel == "voice" else None, location_text=location_text,
                       caller_gps=GeoPoint(lat=gps[0], lon=gps[1]) if gps else None, caller_id=caller_id,
                       settings_snapshot={**defaults(), **snapshot})


def triage_reply(**kw: Any) -> dict[str, Any]:
    """A valid model reply (the keys the Triage prompt asks for)."""
    return {"language": "English", "language_confidence": 0.95, "incident_type": "accident", "type_confidence": 0.9,
            "severity": "high", "severity_confidence": 0.85, "victims_estimate": 3, "victims_confidence": 0.8,
            "location_words": "near Clock Tower", "has_real_details": True, "vague_or_joking": False,
            "overall_confidence": 0.88, **kw}


def ambulance(vid: int, km: float = 1.0, vtype: str = "ambulance") -> VehicleRow:
    return VehicleRow(vehicle_id=vid, vehicle_type=vtype, lat=SCENE[0] + km / 111.2, lon=SCENE[1],
                      patient_capacity=2, station_name=None)


class FakeStore:
    """Implements the C-6 ``PipelineStore`` protocol in memory and records every call in order."""

    def __init__(self, jobs: list[PipelineJob] = (), vehicles: list[VehicleRow] = (),
                 history: dict[int, CallerHistory] | None = None, nearby: int = 0) -> None:
        self.jobs = list(jobs)
        self.vehicles = list(vehicles)
        self.history = history or {}
        self.nearby = nearby
        self.calls: list[tuple[str, Any]] = []
        self.saved: dict[str, Any] = {}
        self.claimed_types: list[frozenset] = []
        self.heartbeats: list[dict[str, Any]] = []
        self.state: dict[int, str] = {j.incident_id: "pending" for j in self.jobs}

    def names(self) -> list[str]:
        return [n for n, _ in self.calls]

    async def claim_next(self, job_types=frozenset({PipelineState.PENDING, PipelineState.REALLOCATE})):
        self.claimed_types.append(job_types)
        await asyncio.sleep(0)
        if not self.jobs:
            return None
        j = self.jobs.pop(0)
        self.state[j.incident_id] = "processing"
        return j

    async def save_transcript(self, incident_id, transcript, transcript_unclear):
        self.calls.append(("save_transcript", incident_id))

    async def save_location(self, incident_id, result):
        self.calls.append(("save_location", incident_id))
        self.saved["location"] = result

    async def save_triage(self, incident_id, result):
        self.calls.append(("save_triage", incident_id))
        self.saved["triage"] = result

    async def save_trust(self, incident_id, assessment):
        self.calls.append(("save_trust", incident_id))
        self.saved["trust"] = assessment

    async def find_duplicate_candidates(self, incident_id, distance_m, window_min):
        self.calls.append(("find_duplicate_candidates", incident_id))
        return []

    async def count_independent_nearby(self, incident_id, distance_m, window_min):
        self.calls.append(("count_independent_nearby", (distance_m, window_min)))
        return self.nearby

    async def get_caller_history(self, caller_id):
        self.calls.append(("get_caller_history", caller_id))
        return self.history.get(caller_id)

    async def save_duplicate_results(self, incident_id, results):
        self.calls.append(("save_duplicate_results", incident_id))

    async def list_available_vehicles(self, types):
        self.calls.append(("list_available_vehicles", types))
        return [v for v in self.vehicles if v.vehicle_type in types]

    async def save_recommendations(self, incident_id, result):
        self.calls.append(("save_recommendations", incident_id))
        self.saved["allocation"] = result

    async def mark_stage_failed(self, incident_id, stage, error):
        self.calls.append(("mark_stage_failed", stage))
        self.saved["error"] = error
        self.state[incident_id] = "failed"

    async def mark_done(self, incident_id):
        self.calls.append(("mark_done", incident_id))
        self.state[incident_id] = "done"

    async def heartbeat(self, worker_id, info):
        self.heartbeats.append({"worker_id": worker_id, **info})
