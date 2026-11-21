# STATUS.md

**Last updated:** 2026-11-20 · **Baseline commit:** `13cf6e6` (branch `main`)
**Overall state:** Repository scaffold plus a working backend test harness. **B1-A1-02 is complete: merged into `main` via PR #5 (`13cf6e6`); CI green on the PR (run 44739714339) and on `main` (run 44740163138).** **B1-A1-03 (contract C-1 v1) is implemented on branch `feat/contract-c1-schemas`, not yet committed: `docker compose run --rm api pytest -q -rs` → 76 passed, 0 failed, 0 skipped (Python 3.11.18, PostGIS).** Planning is pending approval. No application feature is implemented (schemas only).

## 1. Current position

| Item | Value |
|---|---|
| Latest completed work | **B1-A1-03** — contract C-1 v1: enums and Incident Record schemas (see the state above), 2026-11-20. Before it: **B1-A1-02** — backend test harness (complete), 2026-11-20. Before that: **BP-01** — implementation blueprint (`docs/blueprint/`, 14 documents, design sketches with 46 passing sketch tests) — documentation only, 2026-11-20 |
| Before that | DOC-01 SRS/SDS v1.1 (2026-11-20); PLAN-02 team roles (2026-11-19); PLAN-01 audit and plan (2026-11-19) |
| Current task | B1-A1-03 awaiting commit (see above). No other task started |
| Recommended next task | Week-1 decisions (D-001, D-001b, D-027b/D-034, D-031, D-032) → **B1-A2-01** (contract C-2: AI result schemas) |
| Blockers | Team approval; open decisions in DECISIONS_LOG §2 (D-007…D-009, D-013…D-019, D-021…D-029, D-031…D-035) |

## 2. Verified results

| Date | Command | Environment | Result |
|---|---|---|---|
| 2026-11-19 | `cd backend && python3 -m pytest -q` | Audit workspace, no project dependencies, installs disabled | **BLOCKED** — `ModuleNotFoundError: No module named 'fastapi'`; 0 tests executed (superseded by the rows below) |
| 2026-11-20 | `docker compose run --rm api pytest -q -rs` | Docker, **Python 3.11.18**, pinned requirements, PostGIS 15-3.4 container | **6 passed**, 0 skipped (2 API tests + 4 database tests) |
| 2026-11-20 | `docker compose run --rm api pytest -q -rs` (B1-A1-03 working tree) | Same | **76 passed**, 0 failed, 0 skipped (6 earlier + 70 C-1 schema tests) |
| 2026-11-20 | `DATABASE_URL=<localhost variant of .env> backend/.venv/bin/python -m pytest -q -rs` | Local venv, **Python 3.14** (not the project version), same PostGIS container | **6 passed** (secondary evidence only) |
| 2026-11-20 | Same local command with an unreachable database (port 59999) | Local venv, Python 3.14 | **2 passed, 4 skipped**, each skip shows the reason "PostgreSQL not reachable" |
| 2026-11-20 | `cd docs/blueprint/code_sketches && python3 -m pytest -q` | Writing environment, Python 3, no project dependencies needed | **46 passed** — tests of *design sketches*, not of the product |
| 2026-11-20 | Mermaid render of every diagram in `docs/blueprint/*.md` | `mmdc` in the writing environment | All blocks rendered, no errors |
| 2026-11-20 | `python3 docs/blueprint/tools/schedule_check.py` | Writing environment | 0 dependency violations; 70 Batch-1 tasks scheduled (Arjun 23, Khalid 19, Sumeet 28) |

The 2 original tests and 4 new database tests pass in Docker on Python 3.11. CI (`.github/workflows/ci.yml`, with a PostGIS service) succeeded on PR #5 and on `main` (run IDs in the state line at the top); the run logs were not read, so the CI test count is not recorded here.
**Not verified:** LangGraph wiring, library versions, hardware memory estimates.

## 3. Implementation state by area

Legend: ✅ verified · 🟡 exists, not verified · 🟠 partial · ⬜ placeholder · ❌ missing

| Area | State | Evidence / notes |
|---|---|---|
| FastAPI app, CORS (`backend/app/main.py`) | 🟡 | `health` and `reports` routers only |
| `GET /health` | 🟡 | API + DB probe; no worker/OSRM/LLM checks |
| Config (`core/config.py`) | 🟡 | Env settings with SRS Appendix C defaults; no DB-backed settings |
| DB engine/session/Base (`core/db.py`) | 🟡 | Async engine created at import time |
| Report schemas (`schemas/report.py`) | 🟡 | `channel` is the C-1 `Channel` enum (`voice, sms, web, app`); no audio field |
| Contract C-1 (`schemas/enums.py`, `schemas/incident.py`) | ✅ (schemas) | D-005 enums; `IncidentSummaryOut`, `IncidentDetailOut` and nested schemas; tests in `tests/unit/schemas/`. Not yet used by any endpoint |
| `POST /reports` | 🟠 | Validates `description` only; returns hard-coded `INC-000000`; **saves nothing** — must not be demonstrated (NFR-P12) |
| LLM Gateway (`llm/gateway.py`) | 🟠 | Abstract interface only |
| Triage / Trust / Coordination / Resource agents | ⬜ | One docstring each in the repository. Design sketches with tests exist **only** in `docs/blueprint/code_sketches/` (not product code) |
| AI worker, WebSocket hub, models, services | ⬜ | Docstrings / READMEs only |
| Alembic migrations, auth/RBAC, audit, admin, analytics | ❌ | — |
| Dispatch, assignments, tracking, notifications | ❌ | — |
| STT, geocoding, routing integrations | ❌ | — |
| Seed data, simulators, evaluation data, OSRM data, gazetteer | ❌ | `.gitkeep` / READMEs |
| Dashboard, admin panel, public report page | ❌ | `.gitkeep` only |
| Mobile app (citizen/driver) | ❌ | No folder; D-002 approved (React Native), sub-choice open |
| Docker Compose | 🟡 | `postgres` + `api` only |
| CI | 🟡 | `pytest -q -rs` on Python 3.11 with a `postgis/postgis:15-3.4` service; succeeded on PR #5 and `main` (run IDs at the top; logs not read); no frontend job |
| Tests | ✅ | 76 tests pass in Docker/Python 3.11 (70 C-1 schema tests, see §2). Harness: 2 API tests, 4 PostGIS tests (`tests/integration/`), async `client` and rollback `db_connection`/`db_session` fixtures in `tests/conftest.py`. Factories deferred to the model tasks. They test only the harness and `/health`, not product features |

## 4. Known problems

1. `fyp-dispatch/` duplicates the whole repository (D-001).
2. SRS/SDS v1.1 are committed in `docs/srs-sds/` on `main` (via PR #5); the October drafts are no longer on `main`. D-001b: formal team approval of the path decision, if required, is still pending.
3. Code comments cite names not in the SDS (D-003).
4. README and `frontend/README.md` plan a driver PWA; D-002 chose React Native (README not yet updated).
5. `POST /reports` is still a stub: it returns a hard-coded fake reference without saving. The real implementation, B1-A1-16, is **not yet implemented**.
6. `README.md` ownership table is outdated (A-007, D-027b/D-034).
7. SDS v1.1 figures 2.2, 3.1, 4.1, 5.1, 6.3 are images and still show the old design (see CHANGES DOC-01).
8. **Duplicate formula (U-1):** the D-007 linear formula cannot reach the 85 % auto-link threshold at TC-13; D-033 proposes quadratic decay.
9. Twelve unclear or conflicting requirements U-1…U-12 (`docs/blueprint/01_SRS_ANALYSIS.md`).
10. Workload imbalance if D-027b stands (Arjun about 36 of 70 tasks); D-034 proposes 23 / 19 / 28.
11. `IMPLEMENTATION_PLAN.md` still reads v0.2 and cites v1.0 sources; `IMPLEMENTATION_PLAN_UPDATE_v0.3.md` lists the changes.

## 5. Task status

| Batch | Tasks | Status |
|---|---|---|
| Planning and blueprint | PLAN-01, PLAN-02, DOC-01, BP-01 | Done (documentation only); **pending team approval** |
| Batch 1 — Agent 1 | B1-A1-01 … 34 | **B1-A1-02 complete; B1-A1-03 implemented, awaiting commit (see the state line at the top).** B1-A1-01 and 04…34 not started |
| Batch 1 — Agent 2 | B1-A2-01 … 17 | Pending approval (none started) |
| Batch 1 — Agent 3 | B1-A3-01 … 19 | Pending approval (none started) |
| Batches 2–9 | B2-01 … B9-09 | Pending approval (none started) |
