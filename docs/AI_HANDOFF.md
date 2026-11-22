# AI_HANDOFF.md

How the next session, development agent or team member continues the work.

## 1. Where things stand (2026-11-20)
- SRS and SDS were revised to **v1.1** (DOC-01). The implementation **blueprint** (`docs/blueprint/`, start with `00_START_HERE.md`) is written (BP-01). Plan v0.2 plus `IMPLEMENTATION_PLAN_UPDATE_v0.3.md` is **waiting for approval**. Only **B1-A1-02** (the backend test harness) has been implemented; no application feature exists yet. Current state: `STATUS.md`.
- The repository is a scaffold plus the test harness; verified results are in `STATUS.md` §2. No application feature is implemented or verified (`POST /reports` is still a stub).
- Open decisions are in DECISIONS_LOG.md §2. Approved on 2026-11-20: D-002, D-004, D-005, D-006, D-010, D-011, D-012, D-020, D-030. Newly proposed by the blueprint: **D-031…D-035** (and the D-019 extensions).
- The code in `docs/blueprint/code_sketches/` is **design sketch code with 46 tests**, not product code. Reuse the logic when writing the real agents, but follow the task files and ownership rules, not the sketch layout.

## 2. Read before doing anything
1. PROJECT_CONTEXT.md → AGENT_RULES.md → IMPLEMENTATION_PLAN.md + IMPLEMENTATION_PLAN_UPDATE_v0.3.md → STATUS.md → last entries of CHANGES.md → DECISIONS_LOG.md.
2. SRS v1.1 and SDS v1.1 (clean .docx, committed in `docs/srs-sds/`; D-001b path decision). Read the sections named in your task.
3. The blueprint file for your area: database `04`, backend `05`, AI `06`, web `07`, mobile `08`, integration `09`, testing `10`, schedule `11`.
4. `git status`, `git log -5`; confirm STATUS.md matches the code.

## 3. Who is who
Team roles (team slide, A-007): **Arjun Kumar** = AI & backend; **Khalid Hussain** = frontend & UI/UX; **Sumeet Kumar** = database & technical support. All work is done by one developer; there are no separate reviewers (D-027b, D-034 superseded).

## 3a. If you are one of the three Batch 1 agents

| You are | Start with | Your files | You must not touch |
|---|---|---|---|
| **Agent 1 Backend & DB** | B1-A1-02 is complete; start with Phase 1A: B1-A1-03 → (A2's B1-A2-01) → B1-A1-04 → B1-A1-05 | api, core, models, schemas (not `ai.py`), services, ws, main.py, migrations, db/seed, db/sql, backend API/integration tests | agents, llm, workers, integrations, frontend, mobile |
| **Agent 2 AI** | Done or awaiting commit: B1-A2-01, 02, 03, 06, 07, 11, 13, 14. Next: B1-A2-05 (needs D-009), 10, 08/09 (D-007/D-033), 04 | agents, llm, workers, integrations, `schemas/ai.py`, agent tests, ai_eval, db/eval_data, infra/osrm, infra/gazetteer | models, migrations, routes, services, frontend |
| **Agent 3 Frontend/Mobile** | Done or awaiting commit: B1-A3-01, 02 (F1: `frontend/` workspace, typed client, UI kit, EN/UR). Next: F2 = B1-A3-03 report page, F3 = B1-A3-04 login, F4 = B1-A1-20 + queue/review screens (read-only). Run `cd frontend && npm install && npm test` | frontend/**, mobile/**, docs/user-guides | anything under backend/ |

Shared files (`requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/`, `README.md`) change only through a Coordination Request in DECISIONS_LOG.md §4.

## 4. Required checks for every task
- Run the task's tests; record command and actual result in CHANGES.md (passed / failed / blocked / skipped / not executed).
- Safety rules (PROJECT_CONTEXT §6) hold: save before processing, human approval, urgent never waits, careful merging, fake never dispatched, one open assignment per vehicle, lock only at approval, manual mode, audit everything.
- No secrets in code, docs or logs. No new dependency without a D-entry.
- Do not commit or push; present changed files, test results and a summary to the team.

## 5. Known pitfalls
- Code comments in the repository cite names that are not in the SDS (D-003). Follow SDS v1.1 table names.
- The existing `POST /reports` returns a fake reference without saving. Do not demo it before B1-A1-16.
- `backend/pytest.ini` uses `asyncio_mode = auto`, which needs `pytest-asyncio`.
- The audit and blueprint environments could not install packages; use Docker (`docker compose run --rm api pytest -q`) or CI for real results.
- Do not use the linear duplicate formula from the first D-007 text; it cannot pass TC-13 (D-033).
- LangGraph wiring in `06_AI_AGENTS.md` is **not verified**; build a one-node graph first.
- Frontend: after any backend API change run `cd frontend && npm run gen:api` (backend running) and commit `shared/src/api/schema.ts`; `npm run gen:api:check` fails when it is stale. Tokens stay in memory only (no `localStorage`).

## 6. Next recommended action
The next task and the current state are in `STATUS.md` (one place, so this file does not go stale). The developer authorises each task before work starts. Stop and wait for that approval; do not start development on your own.
