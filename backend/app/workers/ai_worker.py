"""AI worker process (SDS §4.5 ai-engine container, §3.1; D-010). Task B1-A2-14.

Run: ``python -m app.workers.ai_worker`` (same image as the API).

* Wakes on ``LISTEN report_pending`` (sent by the intake at commit) and also polls every
  ``poll_s`` seconds, so a lost notification only delays a job, never loses it.
* ``concurrency`` job slots (default 2, ``WORKER_CONCURRENCY``); each claims with
  ``claim_next`` (``FOR UPDATE SKIP LOCKED``), so two slots or two workers never take the same report.
* Heartbeat every ``heartbeat_s`` seconds into ``worker_heartbeats`` (language model readiness;
  speech-to-text is reported as not ready until B1-A2-04).
* Crash recovery: at start and every ``requeue_every_s`` it calls ``requeue_stale_jobs`` (B1-A1-19):
  a job stuck in ``processing`` goes back to ``pending``; after 3 attempts it goes to manual mode.
* SIGTERM / SIGINT: no new job is claimed; jobs already running finish; then the process exits.
* Only ``pending`` jobs are claimed here; ``reallocate`` jobs come with B1-A2-15.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.schemas.enums import PipelineState
from app.services.pipeline_store import PipelineStore

logger = logging.getLogger("app.workers.ai_worker")

JOB_TYPES = frozenset({PipelineState.PENDING})


class Runner(Protocol):  # what the worker needs from the orchestrator
    async def run(self, job: Any) -> Any: ...


class AIWorker:
    def __init__(self, store: PipelineStore, orchestrator: Runner, *, worker_id: str | None = None,
                 concurrency: int = 2, poll_s: float = 2.0, heartbeat_s: float = 10.0,
                 requeue_every_s: float = 60.0, health: Callable[[], dict[str, Any]] | None = None) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self.store = store
        self.orchestrator = orchestrator
        self.worker_id = worker_id or f"ai-worker-{socket.gethostname()}-{os.getpid()}"
        self.concurrency = concurrency
        self.poll_s = poll_s
        self.heartbeat_s = heartbeat_s
        self.requeue_every_s = requeue_every_s
        self.health = health or (lambda: {})
        self.wake = asyncio.Event()
        self.jobs_done = 0
        self.jobs_failed = 0
        self.busy = 0

    def notify(self, *_: Any) -> None:
        """Called on ``NOTIFY report_pending`` (or by tests): wake the idle slots now."""
        self.wake.set()

    async def _sleep(self, stop: asyncio.Event, seconds: float) -> None:
        waiters = [asyncio.ensure_future(stop.wait()), asyncio.ensure_future(self.wake.wait())]
        try:
            await asyncio.wait(waiters, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waiters:
                w.cancel()

    async def _slot(self, n: int, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                job = await self.store.claim_next(JOB_TYPES)
            except Exception:
                logger.exception("slot %s: cannot claim a job (database?); retrying in %.1fs", n, self.poll_s)
                await self._sleep(stop, self.poll_s)
                continue
            if job is None:
                self.wake.clear()
                await self._sleep(stop, self.poll_s)
                continue
            self.busy += 1
            try:
                outcome = await self.orchestrator.run(job)  # a running job is never cancelled by SIGTERM
                if getattr(outcome, "failed", None) is None:
                    self.jobs_done += 1
                else:
                    self.jobs_failed += 1
            except Exception:
                # The job stays 'processing'; requeue_stale_jobs gives it back later (or manual mode after 3 tries).
                self.jobs_failed += 1
                logger.exception("incident %s: pipeline crashed; left for stale-job recovery", job.incident_id)
            finally:
                self.busy -= 1

    async def _every(self, stop: asyncio.Event, seconds: float, fn: Callable[[], Awaitable[Any]], what: str) -> None:
        while not stop.is_set():
            try:
                await fn()
            except Exception:
                logger.exception("%s failed", what)
            await self._sleep_stop_only(stop, seconds)

    @staticmethod
    async def _sleep_stop_only(stop: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    async def beat(self) -> None:
        await self.store.heartbeat(self.worker_id, {
            **self.health(), "concurrency": self.concurrency, "busy": self.busy,
            "jobs_done": self.jobs_done, "jobs_failed": self.jobs_failed,
        })

    async def requeue(self) -> None:
        requeue = getattr(self.store, "requeue_stale_jobs", None)
        if requeue is not None:
            back, failed = await requeue()
            if back or failed:
                logger.warning("stale jobs: %s back to pending, %s to manual mode", back, failed)

    async def run(self, stop: asyncio.Event) -> None:
        logger.info("%s starting with %s slot(s)", self.worker_id, self.concurrency)
        stop_wakes = asyncio.ensure_future(self._forward_stop(stop))
        background = [asyncio.create_task(self._every(stop, self.heartbeat_s, self.beat, "heartbeat")),
                      asyncio.create_task(self._every(stop, self.requeue_every_s, self.requeue, "stale-job recovery"))]
        try:
            await asyncio.gather(*(self._slot(n, stop) for n in range(self.concurrency)))
        finally:
            for t in background:
                await t
            stop_wakes.cancel()
            try:
                await self.beat()  # last heartbeat with the final counters
            except Exception:
                logger.exception("final heartbeat failed")
            logger.info("%s stopped (done=%s failed=%s)", self.worker_id, self.jobs_done, self.jobs_failed)

    async def _forward_stop(self, stop: asyncio.Event) -> None:
        await stop.wait()
        self.wake.set()


# ---------------------------------------------------------------------- process entry point
async def _listen(worker: AIWorker, database_url: str) -> Callable[[], Awaitable[None]]:
    """``LISTEN report_pending`` on its own asyncpg connection; returns a closer. Polling still works without it."""
    import asyncpg

    from app.schemas.events import JOB_NOTIFY_CHANNEL

    conn = await asyncpg.connect(database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    await conn.add_listener(JOB_NOTIFY_CHANNEL, worker.notify)

    async def close() -> None:
        await conn.close()

    return close


async def main() -> int:
    from app.agents.orchestrator import Orchestrator
    from app.agents.triage import TriageAgent
    from app.core.config import get_settings
    from app.llm.gateway import get_llm_client
    from app.services.pipeline_store import PostgresPipelineStore

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    try:
        llm = get_llm_client(settings)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    if not llm.ready:
        logger.warning("language model %s/%s is not configured (LLM_API_KEY?): every report will go to manual mode",
                       llm.provider, llm.model)
    store = PostgresPipelineStore()
    worker = AIWorker(store, Orchestrator(store, TriageAgent(llm)), concurrency=settings.worker_concurrency,
                      health=lambda: {"llm_provider": llm.provider, "llm_model": llm.model, "llm_ready": llm.ready,
                                      "stt_ready": False})
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    close = None
    try:
        close = await _listen(worker, settings.database_url)
    except Exception as exc:
        logger.warning("LISTEN %s unavailable (%s); polling only", "report_pending", exc.__class__.__name__)
    try:
        await worker.run(stop)
    finally:
        if close is not None:
            await close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
