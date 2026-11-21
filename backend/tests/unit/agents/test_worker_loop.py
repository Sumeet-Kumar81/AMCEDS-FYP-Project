"""AI worker loop tests (B1-A2-14): processes jobs then idles, wakes on notify, survives crashes,
heartbeat, stale-job recovery, clean stop (SIGTERM path)."""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys

import pytest

from app.agents.orchestrator import PipelineOutcome
from app.workers.ai_worker import AIWorker
from tests.unit.agents.fakes import FakeStore, job


class Recorder:
    def __init__(self, delay: float = 0, crash_on: set[int] = frozenset()) -> None:
        self.ran: list[int] = []
        self.delay = delay
        self.crash_on = crash_on
        self.started = asyncio.Event()

    async def run(self, j):
        self.started.set()
        await asyncio.sleep(self.delay)
        if j.incident_id in self.crash_on:
            raise RuntimeError("SIMULATED crash")
        self.ran.append(j.incident_id)
        return PipelineOutcome(j.incident_id)


async def until(cond, timeout: float = 3.0) -> None:
    async def wait():
        while not cond():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout)


def worker(store, runner, **kw) -> AIWorker:
    return AIWorker(store, runner, worker_id="SIMULATED-worker", poll_s=kw.pop("poll_s", 0.05),
                    heartbeat_s=kw.pop("heartbeat_s", 0.05), **kw)


async def test_processes_every_job_then_idles_and_stops() -> None:
    store, runner = FakeStore(jobs=[job(i) for i in range(1, 6)]), Recorder()
    w, stop = worker(store, runner), asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await until(lambda: len(runner.ran) == 5)
    await asyncio.sleep(0.15)  # idle: keeps polling, nothing more to do
    stop.set()
    await asyncio.wait_for(task, 3)
    assert sorted(runner.ran) == [1, 2, 3, 4, 5] and w.jobs_done == 5
    assert all(t == frozenset({"pending"}) for t in store.claimed_types)  # reallocate jobs come with B1-A2-15


async def test_notify_wakes_an_idle_worker_before_the_poll_interval() -> None:
    store, runner = FakeStore(), Recorder()
    w, stop = worker(store, runner, poll_s=30), asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await asyncio.sleep(0.05)
    store.jobs.append(job(7))
    w.notify()
    await until(lambda: runner.ran == [7], timeout=2)
    stop.set()
    await asyncio.wait_for(task, 3)


async def test_stop_lets_the_running_job_finish() -> None:
    store, runner = FakeStore(jobs=[job(1), job(2), job(3)]), Recorder(delay=0.2)
    w, stop = worker(store, runner, concurrency=1), asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await asyncio.wait_for(runner.started.wait(), 2)
    stop.set()  # what the SIGTERM handler does
    await asyncio.wait_for(task, 3)
    assert runner.ran == [1] and len(store.jobs) == 2  # job 1 finished; 2 and 3 never claimed


async def test_a_crashing_job_does_not_stop_the_worker() -> None:
    store, runner = FakeStore(jobs=[job(1), job(2), job(3)]), Recorder(crash_on={2})
    w, stop = worker(store, runner, concurrency=1), asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await until(lambda: len(runner.ran) == 2)
    stop.set()
    await asyncio.wait_for(task, 3)
    assert runner.ran == [1, 3] and w.jobs_failed == 1
    assert store.state[2] == "processing"  # left for requeue_stale_jobs, never silently dropped


async def test_heartbeat_reports_readiness_and_counters() -> None:
    store, runner = FakeStore(jobs=[job(1)]), Recorder()
    w = worker(store, runner, health=lambda: {"llm_ready": False, "stt_ready": False})
    stop = asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await until(lambda: runner.ran == [1] and len(store.heartbeats) >= 2)
    stop.set()
    await asyncio.wait_for(task, 3)
    last = store.heartbeats[-1]
    assert last["worker_id"] == "SIMULATED-worker" and last["llm_ready"] is False and last["jobs_done"] == 1
    assert last["concurrency"] == 2


async def test_stale_jobs_are_requeued_at_start() -> None:
    class Store(FakeStore):
        requeued = 0

        async def requeue_stale_jobs(self):
            Store.requeued += 1
            return 0, 0

    w, stop = worker(Store(), Recorder()), asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await until(lambda: Store.requeued >= 1)
    stop.set()
    await asyncio.wait_for(task, 3)


async def test_database_errors_while_claiming_are_retried() -> None:
    class Flaky(FakeStore):
        fails = 2

        async def claim_next(self, job_types=None):
            if Flaky.fails:
                Flaky.fails -= 1
                raise ConnectionError("SIMULATED database down")
            return await super().claim_next(job_types)

    store, runner = Flaky(jobs=[job(1)]), Recorder()
    w, stop = worker(store, runner, concurrency=1), asyncio.Event()
    task = asyncio.create_task(w.run(stop))
    await until(lambda: runner.ran == [1])
    stop.set()
    await asyncio.wait_for(task, 3)


async def test_slots_run_jobs_in_parallel() -> None:
    store, runner = FakeStore(jobs=[job(1), job(2)]), Recorder(delay=0.3)
    w, stop = worker(store, runner, concurrency=2), asyncio.Event()
    started = asyncio.get_running_loop().time()
    task = asyncio.create_task(w.run(stop))
    await until(lambda: len(runner.ran) == 2)
    assert asyncio.get_running_loop().time() - started < 0.55
    stop.set()
    await asyncio.wait_for(task, 3)


def test_concurrency_must_be_positive() -> None:
    with pytest.raises(ValueError):
        AIWorker(FakeStore(), Recorder(), concurrency=0)


def test_unknown_provider_exits_with_an_error() -> None:
    env = {**os.environ, "LLM_PROVIDER": "SIMULATED-none"}
    proc = subprocess.run([sys.executable, "-m", "app.workers.ai_worker"], env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2 and "not supported" in proc.stderr


@pytest.mark.db
def test_the_real_process_stops_cleanly_on_sigterm(test_database_url: str) -> None:
    """Runs against the empty test database (never the development data)."""
    env = {**os.environ, "DATABASE_URL": test_database_url, "LLM_PROVIDER": "groq", "LLM_API_KEY": "", "LOG_LEVEL": "INFO"}
    proc = subprocess.Popen([sys.executable, "-m", "app.workers.ai_worker"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        lines = []
        for line in proc.stdout:  # wait until it is running
            lines.append(line)
            if "starting with" in line:
                break
        proc.send_signal(signal.SIGTERM)
        out, _ = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    text = "".join(lines) + out
    assert proc.returncode == 0 and "stopped" in text, text
    assert "not configured" in text  # an empty key is reported loudly: reports go to manual mode
