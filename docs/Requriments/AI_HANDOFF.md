# AI_HANDOFF.md

How the next session, development agent or team member continues the work.

## 1. Where things stand (2026-11-19)
- Plan v0.1 written; **waiting for approval**. No implementation has started.
- Repository is a scaffold at commit `a0cba20`. See STATUS.md. Nothing is verified yet: tests could not run in the audit environment.
- 29 open decisions in DECISIONS_LOG.md §2. Blocking ones: **D-004** (schema additions), **D-005** (enums), **D-006** (API contract + `/api/v1`), **D-002** (mobile framework), **D-010** (worker hand-off), **D-011** (intake vs AI split).

## 2. Read before doing anything
1. PROJECT_CONTEXT.md → AGENT_RULES.md → IMPLEMENTATION_PLAN.md → STATUS.md → last entries of CHANGES.md → DECISIONS_LOG.md.
2. SRS v1.0 and SDS v1.0 (Claude Project docs; to be committed to `docs/srs-sds/`, D-001b). Read the sections named in your task.
3. `git status`, `git log -5`; confirm STATUS.md matches the code.

## 3. If you are one of the three Batch 1 agents

| You are | Start with | Your files | You must not touch |
|---|---|---|---|
| **Agent 1 Backend & DB** | B1-A1-02 (test harness), then Phase 1A: B1-A1-03 → (A2's B1-A2-01) → B1-A1-04 → B1-A1-05 | api, core, models, schemas (not `ai.py`), services, ws, main.py, migrations, db/seed, db/sql, backend API/integration tests | agents, llm, workers, integrations, frontend, mobile |
| **Agent 2 AI** | B1-A2-01 (after B1-A1-03), then B1-A2-02, 05, 06, 07, 10 in parallel | agents, llm, workers, integrations, `schemas/ai.py`, agent tests, ai_eval, db/eval_data, infra/osrm, infra/gazetteer | models, migrations, routes, services, frontend |
| **Agent 3 Frontend/Mobile** | Review contracts in Phase 1A; B1-A3-01, 02, 05; B1-A3-13 only after D-002 | frontend/**, mobile/** (after D-002), docs/user-guides | anything under backend/ |

Shared files (`requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/`, `README.md`) change only through a Coordination Request in DECISIONS_LOG.md §4.

## 4. Required checks for every task
- Run the task's tests; record command + result in CHANGES.md (passed / failed / blocked / skipped / not executed).
- Safety rules (PROJECT_CONTEXT §6) hold: save-before-process, human approval, urgent never waits, no auto-merge < 85 %, fake never dispatched, one open assignment per vehicle, lock only at approval, manual mode, audit everything.
- No secrets in code, docs or logs. No new dependency without a D-entry.
- Do not commit or push; present changed files, test results and a summary to the team.

## 5. Known pitfalls
- `fyp-dispatch/` duplicates the whole tree. Edit the **root** copies only.
- Existing code comments cite non-SDS-v1.0 names (D-003). Follow SDS v1.0 table names: `incidents`, `settings`, etc.
- The existing `POST /reports` returns a fake reference without saving. Do not demo it before B1-A1-16.
- `backend/pytest.ini` uses `asyncio_mode = auto`, which requires `pytest-asyncio`.
- The audit environment had no package installs; use Docker (`docker compose run --rm api pytest -q`) or CI to get real results.

## 6. Next recommended action
Team reviews IMPLEMENTATION_PLAN.md and DECISIONS_LOG.md, approves or edits the blocking decisions, then authorises **B1-A1-02**.
