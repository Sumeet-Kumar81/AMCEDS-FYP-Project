# CLAUDE.md — AI-Assisted Multi-Channel Emergency Dispatch System (FYP)

Claude Code reads this file at the start of every session. Keep it short; details live in the documents below.

## What this project is
An academic **prototype** (Sukkur IBA University) that helps an emergency dispatcher handle reports from voice, SMS, web and Android. Three AI agents (Triage, Coordination, Resource Allocation) recommend; a **human dispatcher approves every dispatch**. The Trust Scorer is a rule-based component, **not** a fourth agent. All data is simulated. No live Rescue 1122 integration.

## Read in this order at the start of every session
1. `PROJECT_CONTEXT.md` → `AGENT_RULES.md` → `IMPLEMENTATION_PLAN.md` (+ `IMPLEMENTATION_PLAN_UPDATE_v0.3.md`) → `STATUS.md` → the last 3 entries of `CHANGES.md` → `DECISIONS_LOG.md` → `docs/AI_HANDOFF.md`.
2. The SRS/SDS sections named in your task (`docs/srs-sds/`, v1.1). They are the source of truth; the plan and blueprint explain them.
3. The blueprint file for your area in `docs/blueprint/` (`04` database, `05` backend, `06` AI, `07` web, `08` mobile, `09` integration, `10` testing).
4. `git status`, `git branch`, `git log -5`. Then check that STATUS.md matches the real code. Report any difference; do not trust an earlier status blindly.

## Safety rules (highest priority, never trade away)
1. Save the report to the database **before** any AI step. Never return success or a reference number if the save failed.
2. No vehicle is dispatched without an approval by an authenticated dispatcher. Record who and when.
3. High/critical reports are never held back by a trust check or duplicate confirmation.
4. Auto-link duplicates only at match confidence ≥ 85 %; 60–84 % asks the dispatcher; below 60 % stays separate; no answer = stay separate. Linking never hides or closes an incident.
5. A fake report is never dispatched. Low LLM confidence never makes a report fake.
6. A vehicle has at most one open assignment (database partial unique index). Vehicles are locked **only** at approval, never because they appear in a recommendation.
7. If AI, routing or the LLM fails: clear warning, manual dispatch still works, no report lost. Straight-line ETA is labelled "approximate".
8. Driver GPS is accepted only while the driver is on duty.
9. Every AI result, decision and status change is written to the audit log; users cannot edit it.
10. Report page and app show "If life is in danger, also call 1122".

## Architecture in one paragraph
Modular monolith: FastAPI API + a separate AI worker process (same image), PostgreSQL 15 + PostGIS, jobs through the database (`pipeline_state`, `FOR UPDATE SKIP LOCKED`, `LISTEN/NOTIFY`), WebSocket hub for the dashboard, LLM only through the replaceable LLM Gateway, OSRM for routes, React web, React Native Android. Do not turn it into microservices. Do not add a fourth agent.

## Working rules
- **One task at a time**, named by ID (e.g. `B1-A1-02`). Do not start the next task.
- **Before editing:** state the files you will change, why, DB impact, API impact, dependencies and tests, then wait for my approval.
- Smallest complete, testable unit. Type hints, validation, error handling, logging. No TODO stubs, hard-coded success, fake DB calls or mock data presented as real. Anything simulated is labelled SIMULATED.
- Do not delete, rename or overwrite existing files without approval. Check whether a file or module already exists before creating one. Edit only the root copies (`fyp-dispatch/` is a duplicate).
- **Ask before:** installing packages, changing dependencies, changing the schema, resetting or deleting data, any destructive command, adding a library or service not in the SDS stack. Never expose secrets; never commit `.env`.
- Respect file ownership in `AGENT_RULES.md`. Shared files (`requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/`, `README.md`) change only through a coordination request in `DECISIONS_LOG.md` §4.
- A decision that is still OPEN in `DECISIONS_LOG.md` is **not approved**. If your task depends on one, stop and ask.
- If the SRS/SDS is unclear or conflicts with the plan, record it (DECISIONS_LOG) and ask; do not invent a requirement.

## Testing and honesty
- Every task ships with tests. Run them and report the **exact command and result**: passed / failed / blocked / skipped / not executed.
- Never write that something works or passed if you did not run it. A feature is "done" only when code **and** tests are verified.
- Canonical test command (Docker): `docker compose run --rm api pytest -q`. If Docker is not available, say so and mark results "not verified".

## At the end of every task
1. Update `STATUS.md` (real state, verified results, next task).
2. **Append** an entry to `CHANGES.md` (date, task ID, purpose, files, what/why, DB/API impact, tests and results, limitations). Never edit old entries.
3. Update `DECISIONS_LOG.md`, `IMPLEMENTATION_PLAN.md` and `docs/AI_HANDOFF.md` if they changed.
4. Show me: files changed, test results, short summary. **Do not commit or push.** Then stop and wait.
