#!/usr/bin/env python3
"""One-command launcher for the AMCEDS prototype (development helper, Python standard library only).

Run it from anywhere:

    python3 scripts/run_project.py            # start everything (database, API, migrations, seed, AI worker)
    python3 scripts/run_project.py --no-worker  # start without the AI worker
    python3 scripts/run_project.py --no-seed    # skip the SIMULATED sample data
    python3 scripts/run_project.py test         # run the automatic tests
    python3 scripts/run_project.py status       # show what is running
    python3 scripts/run_project.py stop         # stop everything (your data is kept)

It only calls the same Docker commands that are written in the run guide; it never prints the values in
``.env`` and never deletes data. Press Ctrl+C to stop the AI worker; the database and API keep running
until you run ``stop``.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
HEALTH_URL = "http://localhost:8000/health"
DOCS_URL = "http://localhost:8000/docs"
WORKER_NAME = "amceds-ai-worker"  # fixed name, so an old worker can always be found and stopped

# Runs inside the api container. Prints only the HTTP status and model names, never the key.
LLM_CHECK = """
import os, sys, httpx
if os.environ.get("LLM_PROVIDER", "groq") != "groq":
    print("   provider is not groq: model check skipped"); sys.exit(0)
key, model = os.environ.get("LLM_API_KEY", ""), os.environ.get("LLM_MODEL", "")
if not key:
    print("   LLM_API_KEY is empty: the AI will not run (manual mode)"); sys.exit(0)
base = (os.environ.get("LLM_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
try:
    r = httpx.get(base + "/models", headers={"Authorization": "Bearer " + key}, timeout=15)
except httpx.HTTPError as e:
    print("   could not reach Groq (" + type(e).__name__ + "): check the internet connection"); sys.exit(3)
if r.status_code == 401:
    print("   Groq says the API key is wrong or revoked (HTTP 401)"); sys.exit(3)
if r.status_code != 200:
    print("   Groq answered HTTP %d" % r.status_code); sys.exit(3)
ids = sorted(m["id"] for m in r.json().get("data", []))
if model in ids:
    print("   Groq key works and model '%s' is available" % model); sys.exit(0)
print("   model '%s' is NOT available on Groq (retired or misspelled)." % model)
print("   Models you can put in LLM_MODEL: " + ", ".join(i for i in ids if not any(w in i for w in ("guard", "whisper", "orpheus"))))
sys.exit(4)
"""

REQUIRED = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DATABASE_URL", "JWT_SECRET")
OPTIONAL = {
    "LLM_API_KEY": "the AI cannot read reports; every report goes to 'needs check' (manual mode)",
    "SEED_ADMIN_PASSWORD": "the admin test account is not created",
    "SEED_DISPATCHER_PASSWORD": "the dispatcher test account is not created",
    "SEED_DRIVER_PASSWORD": "the driver test accounts are not created",
}


def say(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def compose(*args: str, check: bool = True) -> int:
    """Run ``docker compose <args>`` in the project folder, showing its output live."""
    cmd = ["docker", "compose", *args]
    print("   $ " + " ".join(cmd), flush=True)
    code = subprocess.run(cmd, cwd=ROOT).returncode
    if check and code != 0:
        fail(f"'{' '.join(cmd)}' failed (exit code {code}). Read the messages above.")
    return code


def check_docker() -> None:
    if shutil.which("docker") is None:
        fail("Docker is not installed or not on PATH. Install Docker Desktop / Docker Engine first.")
    if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0:
        fail("'docker compose' is not available. Install the Docker Compose plugin.")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        fail("Docker is installed but not running (or you need permission). Start Docker and try again.")


def read_env() -> dict[str, str]:
    """Read ``.env`` keys. Values are used only to see whether they are empty; they are never printed."""
    if not ENV_FILE.exists():
        fail(f"{ENV_FILE} does not exist. Copy .env.example to .env and fill in the values first:\n"
             "       cp .env.example .env")
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.split(" #")[0].strip().strip('"').strip("'")
    return values


def check_env() -> None:
    say("Checking .env (values are not shown)")
    env = read_env()
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        fail("these settings are empty in .env: " + ", ".join(missing))
    url = env["DATABASE_URL"]
    if "://" in url and "@" in url:
        creds = url.split("://", 1)[1].split("@", 1)[0]
        user, _, password = creds.partition(":")
        if user != env["POSTGRES_USER"] or password != env["POSTGRES_PASSWORD"]:
            fail("the user/password inside DATABASE_URL is not the same as POSTGRES_USER/POSTGRES_PASSWORD.\n"
                 "       Make them match in .env (postgresql+asyncpg://USER:PASSWORD@postgres:5432/DB).")
    for key, effect in OPTIONAL.items():
        if not env.get(key):
            print(f"   WARNING: {key} is empty -> {effect}.")
    print("   .env looks OK.")


def wait_for_api(timeout_s: int = 120) -> None:
    say(f"Waiting for the API at {HEALTH_URL}")
    deadline = time.monotonic() + timeout_s
    last = "no answer"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
                body = resp.read().decode("utf-8", "replace")[:200]
                if resp.status == 200 and '"database":"ok"' in body.replace(" ", ""):
                    print("   API is up: " + body)
                    return
                last = body
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(2)
    compose("logs", "--tail", "40", "api", check=False)
    fail(f"the API was not healthy within {timeout_s} s (last answer: {last}).\n"
         "       'database: down' usually means the password in DATABASE_URL is wrong. API log lines are above.")


def check_llm() -> None:
    say("Checking the Groq API key and model")
    print("   $ docker compose run --rm -T api python -c <Groq check>", flush=True)
    code = subprocess.run(["docker", "compose", "run", "--rm", "-T", "api", "python", "-c", LLM_CHECK],
                          cwd=ROOT).returncode
    if code == 4:
        fail("fix LLM_MODEL in .env (choose one model from the list above), then run this script again.")
    if code != 0:
        print("   WARNING: the AI check did not pass; reports will go to 'needs check' (manual mode).")


def stop_old_worker() -> None:
    """Stop a worker left running from an earlier start, so two workers never take the same reports."""
    found = subprocess.run(["docker", "ps", "-aq", "--filter", f"name=^{WORKER_NAME}$"],
                           capture_output=True, text=True).stdout.strip()
    if found:
        print(f"   An old AI worker ({WORKER_NAME}) is still there: stopping it first.")
        subprocess.run(["docker", "stop", "-t", "30", WORKER_NAME], capture_output=True)
        subprocess.run(["docker", "rm", "-f", WORKER_NAME], capture_output=True)


def run_worker() -> None:
    stop_old_worker()
    cmd = ["docker", "compose", "run", "--rm", "--name", WORKER_NAME, "api", "python", "-m", "app.workers.ai_worker"]
    print("   $ " + " ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, cwd=ROOT)
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n   Stopping the AI worker (it finishes the report it is working on)...", flush=True)
        subprocess.run(["docker", "stop", "-t", "30", WORKER_NAME], capture_output=True)
        try:
            proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        stop_old_worker()  # make sure nothing is left running in the background


def start(args: argparse.Namespace) -> None:
    check_docker()
    check_env()

    say("Building and starting the database and the API")
    compose("up", "-d", "--build")
    wait_for_api()

    check_llm()

    say("Creating / updating the database tables (migrations)")
    compose("run", "--rm", "api", "alembic", "upgrade", "head")

    if args.no_seed:
        say("Skipping the SIMULATED sample data (--no-seed)")
    else:
        say(f"Loading SIMULATED sample data (size {args.size}; running it again adds nothing)")
        compose("run", "--rm", "api", "python", "-m", "app.seed", "--size", args.size)

    print(f"\n   The project is running.\n   - Health check : {HEALTH_URL}\n   - Try the API  : {DOCS_URL}")

    if args.no_worker:
        print("\n   AI worker not started (--no-worker). Stop everything later with:\n"
              "     python3 scripts/run_project.py stop")
        return

    say("Starting the AI worker (it reads new reports). Press Ctrl+C to stop the worker.")
    run_worker()
    print("\n   AI worker stopped. The database and API are still running.\n"
          "   Stop them with: python3 scripts/run_project.py stop")


def stop(_: argparse.Namespace) -> None:
    check_docker()
    say("Stopping the project (the database data is kept)")
    stop_old_worker()
    compose("down")  # never 'down -v': that would delete the database volume


def status(_: argparse.Namespace) -> None:
    check_docker()
    compose("ps", check=False)


def test(_: argparse.Namespace) -> None:
    check_docker()
    check_env()
    say("Running the automatic tests")
    code = compose("run", "--rm", "api", "pytest", "-q", "-rs", check=False)
    print("\n   RESULT: " + ("all tests passed" if code == 0 else f"some tests FAILED (exit code {code})"))
    sys.exit(code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start, stop or test the AMCEDS prototype with Docker.")
    parser.add_argument("command", nargs="?", default="start", choices=("start", "stop", "status", "test"))
    parser.add_argument("--no-worker", action="store_true", help="do not start the AI worker")
    parser.add_argument("--no-seed", action="store_true", help="do not load the SIMULATED sample data")
    parser.add_argument("--size", choices=("small", "full"), default="small", help="sample data size")
    args = parser.parse_args()
    {"start": start, "stop": stop, "status": status, "test": test}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
