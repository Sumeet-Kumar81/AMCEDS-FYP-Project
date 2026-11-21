# CHANGES.md

Permanent, append-only development history. Newest entries at the bottom. Never edit or delete
earlier entries.

Entry format: date · task ID · purpose · files · what changed · why · DB/API impact · tests and results · limitations.

---

## 2026-11-19 · PLAN-01 · Repository audit and implementation planning (documentation only)

- **Purpose:** Read SRS v1.0 and SDS v1.0, audit the repository at commit `a0cba20`, and produce the batch-based implementation plan with three development agents for Batch 1.
- **Type of work:** Documentation and planning only. **No application source code, models, migrations, APIs, frontend, dependencies, Docker or CI files were changed. No files were deleted or renamed. No database operation was run. Nothing was committed or pushed.**
- **Files created:**
  - `PROJECT_CONTEXT.md`: project purpose, scope, architecture, stack, safety rules, business rules, repo layout.
  - `AGENT_RULES.md`: rules for all agents: session start, file ownership, contracts, safety, conventions, testing, git.
  - `IMPLEMENTATION_PLAN.md`: plan v0.1 with Batch 1 (Agent 1: 34 tasks, Agent 2: 17 tasks, Agent 3: 19 tasks) and Batches 2–9, coordination model, draft endpoint list, WebSocket events, risks and testing strategy.
  - `STATUS.md`: verified current state (nothing verified; tests blocked in the audit environment).
  - `CHANGES.md`: this file.
  - `DECISIONS_LOG.md`: 6 recorded approved-by-source decisions, 29 open decisions (D-001…D-029), 7 shared contracts (C-1…C-7).
  - `docs/AI_HANDOFF.md`: continuation instructions.
- **Files modified:** none existing (none of these documents existed before).
- **DB / API impact:** none.
- **Tests executed:** `cd backend && python3 -m pytest -q` → **blocked**: `ModuleNotFoundError: No module named 'fastapi'` (audit environment had no project dependencies and package installation was disabled). 0 tests executed.
- **Other checks:** `diff -rq --exclude=fyp-dispatch --exclude=.git . fyp-dispatch` → no differences (duplicate tree confirmed).
- **Known limitations:** The plan is a draft pending team/supervisor approval. Endpoint list, schema additions and several rules are proposals recorded as open decisions, not approved requirements. CI run history was not inspected.

---

## 2026-11-19 · PLAN-02 · Team work division updated from the team slide (documentation only)

- **Purpose:** The team supplied slide 4 "Team Roles & Responsibilities" (Arjun Kumar = AI & Backend; Khalid Hussain = Frontend & UI/UX; Sumeet Kumar = Database & Technical Support). Planning documents previously used the README ownership table (Sumeet = frontend, Khalid = database), which contradicts the slide.
- **Type of work:** Documentation and planning only. No source code, config, dependency, database or CI change. `README.md` was **not** edited (it still shows the old ownership table; recorded as a known problem). Nothing committed or pushed.
- **Files modified:**
  - `DECISIONS_LOG.md`: added A-007 (team roles, approved by the team slide); marked D-027 resolved; added D-027b (task-level split, assumptions, workload risk, README update); appended decision-history row.
  - `AGENT_RULES.md`: added §3.1 mapping people to workstreams and file areas.
  - `IMPLEMENTATION_PLAN.md`: version 0.1 → 0.2; added §4.0 team-member mapping.
  - `PROJECT_CONTEXT.md`: team row now lists roles.
  - `STATUS.md`: added known problem about the outdated README ownership table.
  - `docs/AI_HANDOFF.md`: added "Who is who" and person labels on the agent table.
- **DB / API impact:** none.
- **Tests executed:** none (documentation change).
- **Known limitations:** The slide gives roles, not tasks. The task-level split (D-027b) is my proposal and needs team confirmation. The slide does not mention the Android app; it is tentatively assigned to Khalid. Arjun carries the largest share (all AI plus the API).

---

## 2026-11-20 · DOC-01 · SRS and SDS revised to v1.1 (documentation only)

- **Purpose:** Remove errors from the authoritative SRS (Nov 5, rev 82) and SDS (Nov 14, rev 72) and write the approved design decisions into them.
- **Type of work:** Documentation only. No application source code, models, migrations, APIs, frontend, dependencies, Docker or CI files were changed. Nothing committed or pushed.
- **Files produced (delivered to the team, not yet in the repository):** `SRS_v1.1_tracked.docx`, `SRS_v1.1_clean.docx`, `SDS_v1.1_tracked.docx`, `SDS_v1.1_clean.docx`. Tracked files show every edit as a Word revision (author "Claude"); clean files have all edits accepted.
- **What changed — errors:** garbled or machine-paraphrased sentences rewritten (SRS §1.1, §2.1, §2.5, §2.6, UC-01–UC-08, UC-13, NFR-S4/S5/S7/S10, NFR-C11; SDS §1.3, §2, §3, §4, §6, §7, §8.1); typos (`audit_logssn`, "TShis", vehicle "locked back"); SRS table captions 1.2.1/1.4.1 → 1.1/1.2; missing UC-05 actors; SDS Group Lead filled; SRS↔SDS mismatches aligned (confidence 0–1 shown as %, channel values, `group_id`, `reference_no`, status vocabulary); contents page numbers recalculated.
- **What changed — decisions written in:** D-002 (React Native), D-004 (schema additions: new SDS Tables 5.12–5.15 and extra columns), D-005 (status vocabularies), D-006 (new SDS §4.6 with REST endpoint and WebSocket event tables), D-010 (database job queue), D-011 (API saves first; worker does speech-to-text and geocoding), D-012 (rule-based Trust Scorer in the Triage step), D-020 (UC-04 5a keeps reports separate). Python fixed at 3.11 and PostgreSQL at 15.
- **Files modified (planning):** `DECISIONS_LOG.md` (A-008, A-009, D-030 added; the decisions above marked APPROVED; contracts C-1, C-4, C-5 status updated), `CHANGES.md` (this entry).
- **DB / API impact:** none in code. The design now defines the schema additions and the endpoint list that B1-A1-03…11 will implement.
- **Checks executed:** both .docx files of each document passed OOXML schema validation; tracked-change validation confirmed every text edit is a revision; text extracted from the clean and tracked-accepted copies is identical; all removed phrases absent and all new content present; full before/after text diff reviewed.
- **Known limitations:** SDS Figures 2.2, 3.1, 4.1, 5.1 and 6.3 are images and still show the old design (no Trust Scorer/LLM Gateway, speech-to-text in the Intake service, no new tables) — they need redrawing. Contents page numbers were computed from a LibreOffice layout and may differ by one page in Word. The repository still holds the Oct drafts in `docs/Requriments/` (D-001b).

---

## 2026-11-20 · BP-01 · Implementation blueprint written (documentation and design sketches only)

- **Purpose:** Answer the master blueprint prompt (SRS analysis, architecture, technology, database, backend, AI agents, frontend, mobile, integration, testing, nine-month roadmap, GitHub workflow, risks) before any application code, using SRS v1.1 and SDS v1.1.
- **Type of work:** Documentation and planning, plus small Python *design sketches* with tests that live inside the blueprint folder. **No application source code, models, migrations, API behaviour, frontend, dependencies, Docker or CI file in the repository was changed.** Nothing committed or pushed.
- **Files created (folder `docs/blueprint/`):** `00_START_HERE.md`, `01_SRS_ANALYSIS.md`, `02_ARCHITECTURE.md`, `03_TECHNOLOGY.md`, `04_DATABASE.md`, `05_BACKEND.md`, `06_AI_AGENTS.md`, `07_FRONTEND.md`, `08_MOBILE.md`, `09_INTEGRATION.md`, `10_TESTING.md`, `11_ROADMAP_9_MONTHS.md`, `12_GITHUB_WORKFLOW.md`, `13_RISKS_AND_ORDER.md`; `code_sketches/` (`schemas_ai.py`, `trust.py`, `policy.py`, `coordination.py`, `allocation.py`, `triage.py`, `pipeline.py`, `test_sketch.py`, `README.md`); `tools/schedule_check.py`.
- **Files modified (planning):** `DECISIONS_LOG.md` (added D-031…D-035, extended D-019, amended note on D-007, history row); `STATUS.md`, `PROJECT_CONTEXT.md` (v1.1 sources, blueprint pointer), `docs/AI_HANDOFF.md`; `IMPLEMENTATION_PLAN_UPDATE_v0.3.md` created because the full plan was not rewritten (see limitations); `CHANGES.md` (this entry).
- **What was found:** (1) the duplicate formula proposed in D-007 cannot reach the 85 % auto-link threshold at TC-13 (best case 80); a quadratic decay reaches 93 (D-033). (2) The proposed 70-task Batch-1 schedule had three dependency orderings that needed clarification (P-1…P-3 in `11_ROADMAP_9_MONTHS.md`). (3) Workload imbalance (D-034). (4) Twelve unclear or conflicting requirements, U-1…U-12 (`01_SRS_ANALYSIS.md`).
- **DB / API impact:** none in code. The blueprint maps the prompt's table list to the SDS schema (D-031) and specifies endpoints already approved in SDS v1.1 Tables 4.3/4.4.
- **Tests executed:**
  - `cd docs/blueprint/code_sketches && python3 -m pytest -q` → **46 passed** (sketches only; they are design models, not the product).
  - Mermaid check (`mmdc`, every Mermaid block in the 14 blueprint files) → all blocks rendered without errors.
  - `python3 docs/blueprint/tools/schedule_check.py` → 0 dependency violations, all 70 Batch-1 tasks scheduled (Arjun 23, Khalid 19, Sumeet 28).
  - **Not executed / not verified:** LangGraph wiring (no install possible), library versions and availability, hardware memory estimates, and the two existing backend tests (still blocked: no FastAPI in the environment).
- **Known limitations:** The blueprint is a proposal pending team approval. D-031…D-035 and earlier open decisions are not approved. Effort estimates in the roadmap are judgement. SDS figures still show the old design (see DOC-01). `IMPLEMENTATION_PLAN.md` itself still reads v0.2 and cites v1.0 sources; the v0.3 update file lists what changes until it is merged into the plan.

---

## 2026-11-20 · B1-A1-02 · Backend test harness and local development environment

- **Purpose:** Make `pytest` run reliably in Docker (Python 3.11) and locally against a real PostGIS test database.
- **Branch:** `feat/test-harness` (from `main` `d529d36`). Commits `6ee85f4` and `2a9356c` exist on the local branch `feat/test-harness`. Not merged into `main`; the branch is not on `origin`; no pull request has been opened.
- **Also on this branch (not part of B1-A1-02 itself):** the SRS/SDS v1.1 `.docx` files were renamed `docs/SRS-SDS/` → `docs/srs-sds/` (commit `2a9356c`, content unchanged) — the D-001b path decision. `PROJECT_CONTEXT.md`, `STATUS.md` and `docs/AI_HANDOFF.md` were updated to the new path; `DECISIONS_LOG.md` D-001b updated (state resolved on this branch; formal team approval, if required, still pending); `AGENT_RULES.md` header changed from SRS/SDS v1.0 to v1.1; `IMPLEMENTATION_PLAN.md` B1-A1-02 given an implementation-status line (task text unchanged).
- **Files created:** `backend/tests/conftest.py` (creates `dispatch_test` with PostGIS if missing, refuses to use the application database, per-test rollback connection and session, in-process `httpx.AsyncClient` fixture, skips with a reason when no server is reachable); `backend/tests/integration/__init__.py`; `backend/tests/integration/test_db_connectivity.py` (4 tests marked `db`).
- **Files modified:** `backend/requirements.txt` (direct dependencies pinned to versions that installed on Python 3.11.18 in Docker; `psycopg2-binary` and `python-jose` deliberately left unpinned/unchanged by approval); `backend/pytest.ini` (`asyncio_default_fixture_loop_scope`, `asyncio_default_test_loop_scope`, `db` marker); `.github/workflows/ci.yml` (PostGIS 15-3.4 service, CI-only throwaway credentials, `pytest -q -rs`); `scripts/dev.sh` (`test` runs `docker compose run --rm api pytest -q`); `backend/tests/api/test_health.py` (uses the shared async `client` fixture; same two behaviours, plus `database` is `ok` or `down`). `STATUS.md` updated. No file under `fyp-dispatch/` was changed. Besides the files listed above, the accompanying documentation files named in the "Also on this branch" bullet were modified, and the two SRS/SDS `.docx` files were renamed (commit `2a9356c`); no other application code, dependency or configuration file changed.
- **Deferred:** factories for users/vehicles/incidents. The tables do not exist yet; they will be added with the model tasks (B1-A1-07…11).
- **DB / API impact:** none to the application database or the API. Created a separate `dispatch_test` database on the local compose PostgreSQL server (it persists in the `pgdata` volume).
- **Pinned direct packages:** fastapi 0.165.0, uvicorn[standard] 0.54.0, pydantic 2.14.4, pydantic-settings 2.16.3, sqlalchemy[asyncio] 2.1.9, asyncpg 0.32.0, geoalchemy2 0.21.0, alembic 1.20.1, bcrypt 5.0.0, python-multipart 0.0.34, httpx 0.28.1, pytest 9.2.0, pytest-asyncio 1.5.0.
- **Tests executed and results:**
  - `docker compose build api` (twice: unpinned, then pinned) → succeeded, exit 0.
  - `docker compose run --rm api pytest -q -rs` (Python 3.11.18, PostGIS container) → **6 passed**.
  - Local venv (Python 3.14), `DATABASE_URL` pointed at the compose PostgreSQL on localhost → **6 passed**.
  - Local venv with an unreachable database → **2 passed, 4 skipped**, skip reasons displayed.
  - **Not verified:** the GitHub Actions workflow (not run), `scripts/dev.sh test` itself (its command was run directly instead), a clean-machine build.
- **Known limitations:** The harness tests only itself and `/health`; no product feature is tested yet. The first build is slow (several minutes). The local run on Python 3.14 is not evidence for Python 3.11. Existing code still has the unprefixed `/reports` stub that returns a fake ID (fixed later by B1-A1-16).

---

## 2026-11-20 · DOC-02 · Status sync after B1-A1-02 was merged (documentation only)

- **Purpose:** Replace wording that described B1-A1-02 as unpushed / not merged / CI not run with the verified state. The B1-A1-02 entry above is left as written; this entry supersedes its stale statements.
- **Verified state:** PR #5 (`feat/test-harness` → `main`) is closed and merged; `main` is `13cf6e6`. GitHub Actions: `ci` succeeded on the pull request (run 44739714339, commit `cb2dbba`) and on `main` (run 44740163138, commit `13cf6e6`). Source: GitHub public API (status and conclusion only; run logs were not read). B1-A1-02 is complete.
- **Corrections to the B1-A1-02 entry above:** (1) "no pull request has been opened / not on origin" is no longer true; (2) "the GitHub Actions workflow (not run)" is now verified green; (3) "`IMPLEMENTATION_PLAN.md` … (task text unchanged)" was inaccurate: the first sentence of the B1-A1-02 "Purpose / behaviour" line was annotated as superseded, the rest is unchanged.
- **Files modified (documentation only):** `STATUS.md` (the single place that states the B1-A1-02 state; other files point to it), `IMPLEMENTATION_PLAN.md` (B1-A1-02 status line and the wording about unchanged task text), `docs/AI_HANDOFF.md`, `DECISIONS_LOG.md` (D-001b), `PROJECT_CONTEXT.md`, `CHANGES.md` (this entry). No code, configuration or `fyp-dispatch/` file changed.
- **Further stale statements fixed in the same branch (found in review):** `IMPLEMENTATION_PLAN.md` header ("No task in this plan has been started", v1.0 sources, baseline labels) and §8 item 2; `docs/AI_HANDOFF.md` Agent 1 row ("start with B1-A1-02"); `PROJECT_CONTEXT.md` §8 (`fyp-dispatch/` "byte-identical" — `diff -rq` of `backend/` now shows `pytest.ini`, `requirements.txt`, `tests/api/test_health.py` differ and `tests/conftest.py`, `tests/integration/` exist only at the root).
- **D-001b:** state resolved on `main`; formal team approval of the path decision, if required, is still pending. No team approval is recorded.
- **Tests:** none executed (documentation change). **Limitations:** the CI test count is not recorded because the run logs were not read.

---

## 2026-11-20 · B1-A1-03 · Contract C-1 v1: enums and Incident Record schemas

- **Purpose:** Fix the shared vocabulary (D-005) and the Incident Record read shape (SRS Table 3.4 / §7.2, SDS v1.1 Tables 5.2, 5.7, 5.8, 5.12) that the API, AI agents, web and mobile apps will use.
- **Branch:** `feat/contract-c1-schemas` from `main` `13cf6e6`. Not committed, not pushed. The branch also carries the DOC-02 documentation sync (restored from a stash before this task).
- **Files created:** `backend/app/schemas/enums.py` (11 `StrEnum`s: D-005 vocabularies plus `DuplicateDecision` from SDS Table 5.12); `backend/app/schemas/incident.py` (`LocationOut`, `IncidentSummaryOut`, `IncidentDetailOut`, `RecommendationOut`, `AssignmentOut`, `DuplicateCandidateOut`, `TrustSignalOut`, `DispatcherDecisionOut`); `backend/tests/fixtures/contracts/incident_detail.json` (SIMULATED); `backend/tests/unit/schemas/__init__.py`, `test_enums.py` (14 tests), `test_incident_schemas.py` (56 tests).
- **Files modified:** `backend/app/schemas/report.py` (`ReportIn.channel` is the `Channel` enum; `mobile` renamed `app`); `DECISIONS_LOG.md` (C-1 row set to v1, contract name `IncidentOut` corrected to `IncidentSummaryOut`, "C-1 notes" added); `IMPLEMENTATION_PLAN.md` (status line under B1-A1-03, C-1 note under B1-A1-16; original task text unchanged); `STATUS.md`; `CHANGES.md` (this entry).
- **What / why:** confidence 0–1 and trust score 0–100 enforced; timezone-aware timestamps; `reference_no` must be `INC-` + 6 or more digits; output models reject unknown fields so drift fails tests; `location` always present ("no location" = `source: "unknown"`; `gps` needs lat/lon; `text` needs address words, coordinates follow after geocoding per D-011); `eta_seconds` and `distance_meters` required (an approximate ETA still has a value, SRS UC-05 5a); `batch_no` starts at 1. The SRS `vehicles` field is carried by `recommendations` + `assignments`.
- **Approval:** C-1 v1 approved on 2026-11-20 by the project developer, who is the only developer and acts as A1, A2 and A3 (DECISIONS_LOG §3, C-1 notes). No separate reviewers.
- **DB impact:** none (no models, migrations or SQL). **API impact:** response shapes defined but not yet used by any endpoint; `POST /reports` now rejects `channel: "mobile"` with 422 and accepts `app` (OpenAPI shows the `Channel` enum). No other route changed.
- **Tests:** `docker compose run --rm api pytest -q -rs` (Python 3.11.18, PostGIS) → **76 passed, 0 failed, 0 skipped**. A mutation check in a scratch copy outside the repository (C-1 rules deliberately broken) made the expected tests fail, confirming they enforce the contract. **Not verified:** GitHub Actions on this branch (not pushed); no linter or type checker is configured.
- **Known limitations:** In the fixture, `ai_details` and `allocation_summary` are placeholder objects until contract C-2 (B1-A2-01) defines their shape; `TrustSignalOut` (`code`, `points`) may be refined by C-2. The C-1 schemas are not yet used by any endpoint (B1-A1-16 and B1-A1-20 do that). `POST /reports` is still the stub that saves nothing.

---

## 2026-11-21 · DOC-03 · Week-1 decisions recorded; duplicate tree removed (B1-A1-01, part)

- **Purpose:** Record the decisions taken by the project developer, who is the only developer, and remove references to the deleted duplicate tree.
- **Decisions:** D-001 approved and done (the developer deleted `fyp-dispatch/`, 62 tracked files); D-031 approved (option a, no extra tables beyond D-004); D-027b and D-034 superseded (one developer does every task). **D-032 (pilot area and dates) is still open** and needs the developer's input. No other decision changed.
- **Deletion check:** before recording D-001, `fyp-dispatch/` was compared with the root at `HEAD`: four files were older versions of root files; the only copy-only files were an outdated `docs/README.md` one-liner and five empty `.gitkeep` placeholders. Nothing else was lost; all of it is in git history.
- **Files modified:** `DECISIONS_LOG.md` (D-001, D-027b, D-031, D-034 status lines), `STATUS.md` (next task, known problems 1 and 10), `PROJECT_CONTEXT.md` (team row; `fyp-dispatch/` line removed from the layout), `CLAUDE.md` (removed "edit only the root copies"), `docs/AI_HANDOFF.md` (team line, pitfall removed, next action), `IMPLEMENTATION_PLAN.md` (status line under B1-A1-01; task text unchanged), `CHANGES.md` (this entry). Deleted: `fyp-dispatch/**` (by the developer).
- **DB / API impact:** none. **Tests:** see below.
- **Known limitations:** B1-A1-01 still needs the `README.md` update. `docs/blueprint/12_GITHUB_WORKFLOW.md` still mentions removing `fyp-dispatch/` as a future step (the blueprint is a dated design document and was left unchanged). Older CHANGES entries mention `fyp-dispatch/` as history.

---

## 2026-11-21 · B1-A2-01 · Contract C-2 v1: AI input/output schemas (+ C-1 v1.1, D-032)

- **Purpose:** Fix exactly what each AI step receives and returns, so results can be stored and displayed and invalid model output can never drive dispatch.
- **Branch:** `feat/contract-c2-ai-schemas` from `main` `7b5b4e4` (C-1 merged via PR #6). Not committed, not pushed.
- **Files created:** `backend/app/schemas/ai.py` (`TriageInput`, `TriageResult`, `GeocodeResult`, `TrustAssessment` + `TrustSignal`, `DuplicateCandidateResult`, `VehicleRecommendation`, `AllocationResult`, `GeoPoint`; C-2 vocabularies `GeocodeSource`, `TrustAction`, `RoutingMode`, `AgentDuplicateDecision`); `backend/tests/unit/agents/__init__.py`; `backend/tests/unit/agents/test_ai_schemas.py` (90 tests); `backend/tests/fixtures/contracts/ai/README.md`; `examples/*.json` (7 SIMULATED examples); `schemas/*.schema.json` (7 exported JSON Schemas, generated from the models).
- **Files modified:** `backend/app/schemas/incident.py` (C-1 v1.1: optional `detail` on `TrustSignalOut`); `backend/tests/fixtures/contracts/incident_detail.json` (trust signals carry `detail`); `backend/tests/unit/schemas/test_incident_schemas.py` (1 test); `DECISIONS_LOG.md` (D-032, C-1 row v1.1, C-2 row v1, C-2 notes); `IMPLEMENTATION_PLAN.md` (status line under B1-A2-01; task text unchanged); `STATUS.md`; `docs/AI_HANDOFF.md` (§6 now points to STATUS.md); `CHANGES.md` (this entry).
- **What / why:** all models reject unknown fields; confidences and similarities 0–1; trust score and match confidence 0–100; triage unknowns are explicit `None` and every key must be present; a location is never guessed; geocode `unknown` has no coordinates and the other sources need them; each trust signal needs a reason; the agent may only propose `auto_linked`/`possible`/`separate`; straight-line routing marks every ETA approximate. Differences from the plan text are recorded as C-2 notes (C-1 wins).
- **Decisions:** C-2 v1 and C-1 v1.1 approved by the project developer (sole developer). D-032 partly decided: pilot area **Sukkur district**; dates not known, roadmap stays in weeks 1–36.
- **DB / API impact:** none. No models, migrations, routes or dependencies changed. The schemas are not yet used by any agent or endpoint.
- **Tests:** `docker compose run --rm api pytest -q -rs` (Python 3.11.18, PostGIS) → **167 passed, 0 failed, 0 skipped**. JSON Schemas generated with `docker compose run --rm --user "$(id -u):$(id -g)" -e UPDATE_CONTRACT_SCHEMAS=1 api pytest -q tests/unit/agents/test_ai_schemas.py`; the normal run then confirmed they are up to date. A mutation check in a scratch copy outside the repository (five C-2 rules deliberately broken) made 21 tests fail as expected. **Not verified:** GitHub Actions on this branch (not pushed); no linter or type checker is configured.
- **Known limitations:** admin-configurable thresholds are not checked by the schemas (the agents will apply them). `TriageResult` is the agent's final output; the raw LLM JSON (without `model`, `prompt_version`, `latency_ms`) is validated by B1-A2-03. D-018 (hospital rule) and D-035 (trust when triage fails) are still open.

