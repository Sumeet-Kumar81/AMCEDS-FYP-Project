# AGENT_RULES.md

Rules for every development agent (AI or human) working on this repository. They apply in every
batch. If a rule here conflicts with SRS/SDS v1.0, the SRS/SDS win and the conflict is logged in
DECISIONS_LOG.md.

## 1. Start of every session
1. Read PROJECT_CONTEXT.md, this file, IMPLEMENTATION_PLAN.md, STATUS.md, the latest CHANGES.md entries, DECISIONS_LOG.md and docs/AI_HANDOFF.md.
2. Run `git status` and `git log -5`. Preserve any uncommitted work.
3. Check that STATUS.md still matches the code. If it does not, report the difference before working.
4. Read the SRS/SDS sections named in your task.

## 2. One task at a time
- Work only on an approved task ID from IMPLEMENTATION_PLAN.md.
- Before editing, state: task ID, files to change, expected behaviour, DB impact, API impact, tests.
- Implement the smallest complete, testable unit. No TODO placeholders, hardcoded success responses or fake DB operations reported as done.
- Simulated components must be labelled `SIMULATED` in code, UI and docs.

## 3. File ownership (Batch 1 onward)

| Owner | Owns (may edit freely) |
|---|---|
| **Agent 1 — Backend & Database** | `backend/app/api/`, `backend/app/core/`, `backend/app/models/`, `backend/app/schemas/` (except `ai.py`), `backend/app/services/`, `backend/app/ws/`, `backend/app/main.py`, `backend/migrations/`, `backend/alembic.ini`, `backend/tests/api/`, `backend/tests/integration/`, `backend/tests/unit/services/`, `backend/tests/conftest.py`, `db/seed/`, `db/sql/` |
| **Agent 2 — AI & Intelligent Processing** | `backend/app/agents/`, `backend/app/llm/`, `backend/app/workers/`, `backend/app/integrations/` (routing, geocoding, speech-to-text), `backend/app/schemas/ai.py`, `backend/tests/unit/agents/`, `backend/tests/ai_eval/`, `db/eval_data/`, `infra/osrm/`, `infra/gazetteer/` |
| **Agent 3 — Frontend, Mobile & UX** | `frontend/**`, `mobile/**` (proposed, D-002), `docs/user-guides/` |
| **Shared (change by request only)** | `backend/requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/`, `README.md`, root planning docs |

### 3.1 Who does the work (team slide, DECISIONS_LOG A-007; task split D-027b pending confirmation)

| Person | Role | Workstreams |
|---|---|---|
| **Arjun Kumar** | AI & Backend development | Agent 2 (all) + Agent 1 API/services/contracts |
| **Khalid Hussain** | Frontend & UI/UX development | Agent 3 (web, dashboard, alerts, dispatcher interfaces; Android app pending confirmation) |
| **Sumeet Kumar** | Database & technical support | Agent 1 database (models, migrations, seed, SQL), datasets, testing, documentation, deployment support |

Two people may work inside the *Agent 1* area (Arjun on API/services, Sumeet on database). They do not
edit the same files at the same time: Sumeet owns `backend/app/models/`, `backend/migrations/`,
`db/`, `backend/tests/conftest.py`, `.github/`; Arjun owns `backend/app/{api,services,ws,core,schemas}`
and `main.py`, except that Sumeet writes the services named in D-027b (settings, audit, pipeline
persistence, admin, analytics).

Changing a file you do not own: write a **Coordination Request** (CR-xxx) in DECISIONS_LOG.md §4,
get the owner's agreement, then the owner (or you, with agreement) makes the change.

## 4. Shared contracts
- Contracts are listed in DECISIONS_LOG.md §3 with an owner and a version.
- Producers must not change a contract without bumping its version and notifying consumers.
- Consumers must not invent endpoints, fields, event names or AI output formats. Use the OpenAPI schema (`/openapi.json`) and `docs/API_CONTRACT.md`.
- No duplicate models, services or business logic: business rules live once (trust in `agents/trust.py`, vehicle rules in `agents/resource.py`, locking in `services/dispatch.py`).

## 5. Safety rules (never break)
Save before processing · human approval for every dispatch · high/critical never held · no auto-merge below 85 % · fake never dispatched · max one open assignment per vehicle · lock only at approval · manual mode when AI/routing fails · approximate ETA labelled · audit every AI result, decision and status change · simulated data only.

## 6. Code conventions
- Python: type hints, Pydantic v2 schemas, async SQLAlchemy, parameterised queries only, SQL in services/repositories never in routers, `logging` not `print`, UTC timestamps (display UTC+5 in clients).
- Naming: snake_case DB columns and JSON fields; enum values lower snake_case (`needs_check`, `fire_truck`).
- Secrets only from environment variables; never in code, docs, logs or commits.
- Frontend: typed API client from OpenAPI; severity colours red=critical, orange=high, blue=medium, green=low on every screen (SDS §7.6).

## 7. Dependencies and destructive actions
Ask first (DECISIONS_LOG entry + approval) before: adding/upgrading a dependency, changing the DB schema outside an approved task, changing Docker config, deleting/renaming files, resetting databases, or any destructive operation.

## 8. Testing
- Every task ships tests and runs them. Record the exact command and result.
- Status words: **passed, failed, blocked, skipped, not executed**. Never claim a pass that did not run.
- Base verification on SDS §8 test cases (TC-01 … TC-52) and Table 8.3 AI evaluation.

## 9. Git
- Branch `feat/<module>-<name>` from `main`; never push to `main` directly; never force-push or rewrite history.
- Do not commit or push automatically: present changed files, test results and a summary to the team first.
- Commit style: `feat(triage): add json schema validation`.

## 10. End of every task
Update STATUS.md, append to CHANGES.md (date, task ID, files, what/why, DB/API impact, tests and results, limitations), update DECISIONS_LOG.md and docs/AI_HANDOFF.md if affected. Then stop and wait for review.
