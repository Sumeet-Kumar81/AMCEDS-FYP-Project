# IMPLEMENTATION_PLAN.md

**Project:** AI-Assisted Multi-Channel Emergency Dispatch System with Three Specialized Agents
**Plan version:** 0.2 (draft for approval; 0.2 adds team roles) · **Prepared:** 2026-11-19 · **Baseline commit (when written):** `a0cba20` (`main`)
**Sources (when written):** SRS v1.0, SDS v1.0, repository audit, DECISIONS_LOG.md. **Superseded: SRS/SDS v1.1 are authoritative** (see `IMPLEMENTATION_PLAN_UPDATE_v0.3.md`).
**Approval status:** ⏳ **Plan still pending team approval.** Only B1-A1-02 is complete (current state: `STATUS.md`); no other task has been started.

---

## 0. How to read this plan

- Work is organised as **Batches → Phases → Tasks**. Batch 1 is split into **exactly three development agents**.
- Task IDs: `B1-A1-07` = Batch 1, Agent 1, task 7. Later batches use `B3-04` and name the responsible agents.
- Each task lists: purpose and behaviour, approach, traceability (SRS feature/UC/NFR, SDS section, test case), agent, dependencies, files (existing to modify / new), DB impact, API impact, integration, tests, acceptance criteria, priority and output.
- Priority: **P0** = safety or blocking path · **P1** = required by SRS "must" · **P2** = SRS "should" or polish.
- `D-xxx` = open decision, `C-x` = shared contract (DECISIONS_LOG.md). A task that depends on an open decision cannot start until that decision is approved.
- File paths were checked against the repository. Paths marked *(proposed)* do not exist yet; the reason for the location is given.

---

## 1. Implementation strategy (summary)

1. **Agree contracts first (Phase 1A).** Enums, the Incident Record schema, AI output schemas, auth shapes, the endpoint list, WebSocket events and the worker persistence interface are fixed before parallel coding starts. This keeps the three agents from guessing each other's formats.
2. **Build in parallel against contracts (Phases 1B–1D).** Agent 1 builds the database and APIs, Agent 2 builds the AI pipeline against fakes of the DB interface and deterministic LLM fakes, Agent 3 builds screens against the OpenAPI schema and a labelled mock server. Each agent tests its own work in isolation.
3. **Integrate along the report's life (Batches 2–3).** First report → AI → dashboard; then approve → driver → tracking → trip completion.
4. **Add simulated outside world (Batch 4).** SMS/voice channel simulators, vehicle movement simulator and scenario data.
5. **Finish secondary features, harden and measure (Batches 5–8).** Admin/reporting, manual mode and safety validation, security and deployment, performance and AI evaluation.
6. **Document and demonstrate (Batch 9).** User guides, test reports, demo video, final acceptance with supervisors.

```
Batch 1 ─ 1A Contracts (A1+A2+A3, sequential) ─► 1B Foundations (parallel) ─► 1C Core features (parallel) ─► 1D Secondary features (parallel)
Batch 2 ─ End-to-end report pipeline (A1+A2 lead, A3)
Batch 3 ─ Dispatch, driver and live-tracking workflow (A1+A3 lead, A2)
Batch 4 ─ Simulated channels, fleet and scenarios (A1+A2, A3)
Batch 5 ─ Administration, reporting and analytics integration (A1+A3)
Batch 6 ─ Manual mode, resilience and safety validation (all)
Batch 7 ─ Security hardening and Docker deployment (A1 lead, all)
Batch 8 ─ Performance and AI evaluation (A2 lead, all)
Batch 9 ─ Documentation, demo and final acceptance (all)
```

---

## 2. Current state baseline (from the audit — details in STATUS.md)

| Classification | Items |
|---|---|
| **Existing, verified** | None. The two existing tests could not run in the audit environment (FastAPI not installed; package installs disabled). |
| **Existing, unverified** | FastAPI app + CORS (`backend/app/main.py`); `GET /health` with DB probe; `Settings` config with business-rule defaults; async engine/session + `Base`; `ReportIn`/`ReportOut` schemas; `docker-compose.yml` (postgres+PostGIS, api); `backend/Dockerfile`; CI workflow (pytest on Python 3.11); `tests/api/test_health.py` (2 tests); `.env.example`; `.gitignore`; `scripts/dev.sh` |
| **Partially implemented** | `POST /reports` — validates `description` only and returns hard-coded `INC-000000`; **saves nothing** (must not be used as if it worked; violates NFR-P12 until B1-A1-16). `LLMClient` abstract interface only. |
| **Placeholders (docstring only)** | `agents/triage.py`, `agents/trust.py`, `agents/coordination.py`, `agents/resource.py`, `workers/ai_worker.py`, `ws/hub.py`, `models/README.py`, `services/README.md` |
| **Missing** | All DB models and migrations; auth/RBAC; all services; all other endpoints; WebSocket; worker; all agents; STT; routing/geocoding; notifications; seed data; simulators; eval data; OSRM setup; every frontend screen; the mobile app; nginx/TLS; ai-worker/osrm/web containers |
| **Repository issues** | Duplicate tree `fyp-dispatch/` (D-001); SRS/SDS not committed (D-001b); comments cite a non-SDS-v1.0 design (D-003); README plans a PWA for drivers (D-002); `ReportIn.channel` uses `mobile` instead of SDS `app` (D-005); error text says "description or audio" but no audio field exists |

No existing functionality is counted as complete in this plan.

---

## 3. Development areas → batches

| Area | Batch 1 owner | Integrated in |
|---|---|---|
| Database (PostGIS, models, migrations, seed) | A1 | B2–B5 |
| REST API, auth, RBAC, audit, admin, analytics | A1 | B2–B5 |
| Intake (web/app/voice/SMS) | A1 (+A2 STT) | B2, B4 |
| AI pipeline: Triage, trust, Coordination, Resource Allocation, orchestrator, worker | A2 | B2, B8 |
| Routing / geocoding / speech-to-text integrations | A2 | B2, B3 |
| Real-time WebSocket + notifications | A1 | B2, B3 |
| Dispatcher dashboard, review queue, live map, admin, reports | A3 | B2, B3, B5 |
| Public report page + citizen app | A3 | B2, B4 |
| Driver app | A3 | B3 |
| Simulators (SMS, voice, vehicles), scenarios | B4 (A1, A2, A3) | B4, B8 |
| Testing / performance / AI evaluation | each agent + B6, B8 | B6, B8 |
| Deployment (Docker Compose, nginx TLS) | B7 (A1 lead) | B7 |

---

## 4. Coordination model for the three agents

### 4.0 Team members and agents (DECISIONS_LOG A-007, D-027b)
The three *agents* are workstreams; people own them:

| Person (role from team slide) | Agents / workstreams | Batch 1 tasks (proposed, D-027b) |
|---|---|---|
| **Arjun Kumar** — AI & Backend | Agent 2 (all); Agent 1 API, services, contracts | A2-01…15, 17; A1-03, 04, 05, 14–18, 20–30, 33 |
| **Khalid Hussain** — Frontend & UI/UX | Agent 3 (dashboard, public page, alerts, dispatcher interfaces; Android app pending) | A3-01…19 |
| **Sumeet Kumar** — Database & technical support | Agent 1 database, datasets, testing, documentation, deployment | A1-01, 02, 06–13, 19, 31, 32, 34; A2-16; OSRM/gazetteer data; later batches: simulators, test reports, deployment, user guides |

Later batches name agents; map them to people with this table. Batch 6–9 testing, documentation and deployment tasks are led by Sumeet with Arjun and Khalid contributing their areas.

### 4.1 Ownership
File ownership is defined in AGENT_RULES.md §3 and summarised here:

| Agent | Owns | Never edits without a CR |
|---|---|---|
| **A1 Backend & DB** | `backend/app/{api,core,models,schemas*,services,ws,main.py}`, `backend/migrations/`, backend API/integration tests, `db/seed/`, `db/sql/` (*except `schemas/ai.py`) | agents, llm, workers, integrations, frontend, mobile |
| **A2 AI & Processing** | `backend/app/{agents,llm,workers,integrations}/`, `backend/app/schemas/ai.py`, agent unit tests, `tests/ai_eval/`, `db/eval_data/`, `infra/osrm/`, `infra/gazetteer/` | models, migrations, API routes, services, frontend |
| **A3 Frontend/Mobile/UX** | `frontend/**`, `mobile/**` *(proposed, D-002)*, `docs/user-guides/` | anything under `backend/` |
| Shared (CR required) | `backend/requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/`, `README.md`, root docs | — |

`backend/app/integrations/` *(proposed)*: a new package for outside-service clients (OSRM, geocoder, speech-to-text). The scaffold has no suitable package; `services/` is reserved for A1 business logic (`services/README.md`).

### 4.2 Shared contracts and the order they are agreed

| Order | Contract | Owner → consumers | Agreed in task | Why this order |
|---|---|---|---|---|
| 1 | C-1 Enums + Incident Record schemas | A1 → A2, A3 | B1-A1-03 | Every other contract uses these values |
| 2 | C-2 AI result schemas | A2 → A1, A3 | B1-A2-01 | A1 needs them to design storage; A3 to design review screens |
| 3 | C-3 Auth shapes and roles | A1 → A3 | B1-A1-04 | Needed for every private screen |
| 4 | C-4 REST endpoint list | A1 → A3, A2 | B1-A1-04 | Uses C-1, C-2, C-3 |
| 5 | C-5 WebSocket events + NOTIFY payloads | A1 → A3, A2 | B1-A1-05 | Uses C-1/C-2 ids; worker emits |
| 6 | C-6 Pipeline persistence interface | A1 → A2 | B1-A1-05 | Worker writes through it |
| 7 | C-7 Driver assignment payload + transitions | A1 → A3 | B1-A1-05 | Driver app depends on it |

**Integration points (where work meets):**
- **IP-1** worker ↔ DB through `services/pipeline_store.py` (C-6). A2 codes against a fake; A1 implements the real one; joined in B2-01.
- **IP-2** worker → API → dashboard events through Postgres NOTIFY → WebSocket hub (C-5). Joined in B2-02.
- **IP-3** API ↔ AI for re-allocation after dispatcher edits/declines (pipeline_state `reallocate`). Joined in B2-04 / B3-04.
- **IP-4** API ↔ routing integration for the driver route proxy (`GET /api/v1/routing/route`). Joined in B3-03.
- **IP-5** Web and mobile ↔ REST (C-3, C-4, C-7) through a client generated from `/openapi.json`. Joined in B2-03, B3-02.

**Likely conflicts and how they are avoided:**
- *Two places computing business rules:* trust only in `agents/trust.py`; vehicle counts only in `agents/resource.py`; locking only in `services/dispatch.py`. The API never recomputes AI rules; the UI never recomputes anything.
- *Schema drift between `schemas/ai.py` (A2) and DB JSONB columns (A1):* A1 stores the `model_dump()` of C-2 objects; contract tests in both agents load the same JSON fixtures from `backend/tests/fixtures/contracts/` *(proposed, A1 owns; A2 adds AI fixtures by CR)*.
- *`requirements.txt` edits by several agents:* each dependency goes through a D-entry; A1 merges.
- *Frontend inventing fields:* A3 uses only generated types; mock server data must come from contract fixtures and be labelled MOCK.

### 4.3 Proposed REST endpoints (C-4 draft — to be approved under D-006)

All under `/api/v1`. Roles: P = public, D = dispatcher, R = driver, A = admin, S = simulator secret.

| Area | Method & path | Role | UC / TC |
|---|---|---|---|
| Health | `GET /health` (api, db, worker heartbeat, osrm, llm, geocoder) | P | NFR-S5, TC-45 |
| Intake | `POST /reports` (JSON text report; `client_request_id` for idempotency) | P | UC-01, TC-01/03/04/50 |
| Intake | `POST /reports/voice` (multipart audio ≤ 2 min, WAV/MP3/M4A + same fields) | P | UC-01 2a, TC-02 |
| Intake | `POST /reports/{reference_no}/confirmation` (caller confirms via token link/app) | P (token) | UC-03 6, TC-12 |
| Intake (sim) | `POST /intake/sms`, `POST /intake/voice` | S | UC-01 SMS/voice, D-014 |
| Auth | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` | P / any | UC-11, TC-32 |
| Incidents | `GET /incidents` (filters: status, severity, type; sort severity desc then received_at) | D | UC-06 1 |
| Incidents | `GET /incidents/{id}` (record + AI details + trust signals + duplicates + current recommendations + assignments) | D | UC-06 1 |
| Incidents | `PATCH /incidents/{id}` (type, severity, victims, location) → triggers re-allocation | D | UC-06 2, TC-23 |
| Incidents | `GET /incidents/{id}/audio` | D | UC-01 2a |
| Duplicates | `POST /duplicate-candidates/{id}/confirm`, `POST /duplicate-candidates/{id}/reject` | D | UC-04 5 |
| Review | `GET /review-queue` | D | UC-07 1 |
| Review | `POST /incidents/{id}/confirmation-requests` | D | UC-07 2 |
| Review | `POST /incidents/{id}/review-decision` `{decision: real|fake|need_info, note}` | D | UC-07 3, TC-24/25 |
| Dispatch | `POST /incidents/{id}/dispatch` `{vehicle_ids[], hospital_id?, override_reason?}` → 201 or 409 with next-best | D | UC-06 3–4, TC-21/22/46 |
| Dispatch | `PATCH /assignments/{id}/hospital`, `POST /assignments/{id}/cancel` | D | UC-09 2a |
| Fleet | `GET /vehicles` (filters type, status, near), `GET /fleet/live` snapshot | D | UC-10, manual mode |
| Hospitals | `GET /hospitals` | D, R | UC-09 |
| Routing | `GET /routing/route?from=lat,lon&to=lat,lon` (OSRM proxy; CI-6 keeps OSRM private) | R, D | UC-08 3 |
| Driver | `POST /driver/duty/start`, `POST /driver/duty/end` | R | UC-11 2–3, TC-33 |
| Driver | `GET /driver/assignments/current` | R | UC-08 |
| Driver | `POST /driver/assignments/{id}/accept`, `POST …/decline {reason_code}` | R | UC-08 2/2a, TC-26/27 |
| Driver | `POST /driver/assignments/{id}/status {on_scene|picked_up|at_hospital|available, source: auto|manual}` | R | UC-09, TC-29 |
| Driver | `POST /driver/locations` (batch of points, for offline buffering) | R (on duty) | UC-08 4, CI-7, NFR-C5 |
| Admin | `GET/POST/PATCH /admin/users[/{id}]` (disable, not delete) | A | UC-12 2 |
| Admin | `GET/POST/PATCH/DELETE /admin/vehicles[/{id}]` | A | UC-12 3, TC-34/35 |
| Admin | `GET/POST/PATCH /admin/hospitals[/{id}]` | A | UC-12 4 |
| Admin | `GET /admin/settings`, `PUT /admin/settings/{key}` | A | UC-12 5, TC-36 |
| Admin | `GET /admin/audit-logs` (read-only) | A | NFR-S9 |
| Analytics | `GET /analytics/incidents` (period, type, status; timeline) | D, A | UC-13 2 |
| Analytics | `GET /analytics/performance` (triage accuracy, duplicate rate, ETA error, response time AI vs manual) | D, A | UC-13 3 |
| Analytics | `GET /analytics/export?format=csv|pdf` | D, A | UC-13 4, TC-37 |
| WebSocket | `GET /ws?token=…` | D, R | CI-2 |

### 4.4 WebSocket events (C-5 draft)

Envelope: `{"event": "<name>", "v": 1, "occurred_at": "<UTC ISO>", "data": {...}}`. Channels: `dispatchers` (all dispatcher sessions), `driver:<user_id>`.

| Event | Channel | Emitted by | Data |
|---|---|---|---|
| `incident.created` | dispatchers | API (intake) | incident summary |
| `incident.updated` | dispatchers | API / worker via NOTIFY | id, changed fields, pipeline_state |
| `incident.ai_failed` | dispatchers | worker via NOTIFY | id, stage, error code (manual mode) |
| `review.item_added` / `review.item_resolved` | dispatchers | worker / API | id, reasons |
| `duplicate.candidate` | dispatchers | worker | candidate id, both incident ids, confidence |
| `recommendation.ready` | dispatchers | worker | incident id, batch_no, shortage flag |
| `dispatch.approved` | dispatchers | API | incident id, assignments |
| `assignment.new` / `assignment.updated` | driver:<id> | API | C-7 payload |
| `assignment.accepted` / `.declined` / `.timed_out` / `.status_changed` | dispatchers | API | assignment id, status, times |
| `vehicle.position` | dispatchers | API | vehicle id, lat, lon, speed, recorded_at, eta_seconds? |
| `vehicle.signal_lost` / `vehicle.signal_restored` | dispatchers | API scheduler | vehicle id, last position |
| `system.service_status` | dispatchers | API health monitor | per-service up/down (manual-mode banner) |

### 4.5 Database (SDS §5.2 + D-004 additions)

SDS tables: `callers, incidents, incident_groups, users, vehicles, vehicle_locations, recommendations, assignments, hospitals, audit_logs, settings`. Proposed additions (D-004): new tables `duplicate_candidates`, `confirmation_requests`, `user_sessions`, plus columns listed in DECISIONS_LOG D-004. All geometry columns `geometry(Point, 4326)` with GiST indexes; all timestamps `timestamptz` UTC.

### 4.6 Change control between agents
1. Write a CR in DECISIONS_LOG.md §4. 2. The owner accepts or proposes an alternative. 3. The owner implements, or the requester implements on a branch with the owner reviewing. 4. Bump the contract version and update fixtures. 5. Consumers adapt in their next task.

---

# BATCH 1 — THREE SPECIALIZED DEVELOPMENT AGENTS

**Objective:** build the full application foundation and every main functional area, each tested in
isolation, so later batches only integrate, simulate, harden and measure.

**Entry condition:** this plan approved; D-001 (optional), D-004, D-005, D-006 approved before Phase 1A closes; D-002 approved before B1-A3-13.

**Exit condition (Batch 1 done):** every B1 task meets its acceptance criteria with tests run and recorded; contracts C-1…C-7 at v1; no cross-agent file edits without a CR.

### Phase plan

| Phase | Tasks | Mode |
|---|---|---|
| 1A Contracts | B1-A1-03 → B1-A2-01 → B1-A1-04 → B1-A1-05; A3 reviews each (B1-A3-01 starts in parallel) | Sequential, all agents review |
| 1B Foundations | A1: 01, 02, 06–13 · A2: 02, 05 (data), 10 (OSRM infra), 16 · A3: 01, 02, 05, 13 | Parallel |
| 1C Core features | A1: 14–30 · A2: 03, 04, 06–09, 11–15 · A3: 03, 04, 06–10, 14–18 | Parallel (within an agent, follow dependencies) |
| 1D Secondary features | A1: 31–34 · A2: 17 · A3: 11, 12, 19 | Parallel |

---

## Agent 1 — Backend and Database Development Agent

**Mission:** FastAPI modular monolith, PostgreSQL/PostGIS schema, Alembic migrations, Pydantic
schemas, REST APIs, auth/RBAC, intake, incidents, review, duplicates, dispatch, assignments, fleet,
tracking, WebSocket, notifications, admin, analytics, audit, seed data, and the persistence interface
used by the AI worker. Follows SDS §4–§6 and does not redesign the architecture.

#### B1-A1-01 — Repository hygiene
- **Implementation status (2026-11-21):** partly done — `fyp-dispatch/` deleted (D-001) and the SRS/SDS v1.1 are in `docs/srs-sds/` (D-001b). Still open: the `README.md` update (source of truth, ownership table, PWA wording). The original task text below is unchanged.
- **Purpose / behaviour:** Leave one canonical source tree and commit the approved SRS/SDS so every agent reads the same documents.
- **Approach:** After D-001 approval, remove `fyp-dispatch/` (identical copy) in a dedicated PR. After D-001b, add the two `.docx` files to `docs/srs-sds/`. Update README "Source of truth" and ownership (D-027).
- **Traceability:** NFR-P18 (maintainability); SDS §4.4 (layered design for parallel teams).
- **Depends on:** D-001, D-001b, D-027. **Files — modify:** `README.md`; **delete (approved only):** `fyp-dispatch/**`; **new:** `docs/srs-sds/*.docx`.
- **DB / API impact:** none.
- **Integration:** all agents rebase after merge.
- **Tests:** `diff -rq` before deletion is recorded in CHANGES.md; CI still green.
- **Acceptance:** one tree; SRS/SDS present; README accurate. **Priority:** P1. **Output:** cleanup PR.

#### B1-A1-02 — Backend test harness and local development environment
- **Implementation status:** **Complete** — current state in `STATUS.md`. **Deferred:** factories for users/vehicles/incidents (to the model tasks B1-A1-07…11). Details: `CHANGES.md` entry B1-A1-02. Only the first sentence of "Purpose / behaviour" below is annotated as superseded; the rest of the task text is unchanged.
- **Purpose / behaviour:** *(Original wording: "The two existing tests have never been shown to pass." — superseded; see the implementation status above: they now pass in Docker on Python 3.11.)* Make `pytest` run reliably locally, in Docker and in CI, with a real PostGIS test database for integration tests.
- **Approach:** Pin versions in `requirements.txt` (CR to self as owner of shared file, logged). Add `backend/tests/conftest.py` with: an async engine to `dispatch_test`, per-test transaction rollback, a `client` fixture (`httpx.AsyncClient` + ASGI transport), factories for users/vehicles/incidents. Integration tests marked `@pytest.mark.db` and skipped with a clear reason when no DB. Add `docker compose run --rm api pytest -q` to `scripts/dev.sh test`. CI: add a `postgis/postgis:15-3.4` service so DB tests run in CI.
- **Traceability:** SDS §8.1 (pytest for backend and agents); NFR-P18.
- **Depends on:** none. **Files — modify:** `backend/requirements.txt`, `backend/pytest.ini`, `.github/workflows/ci.yml`, `scripts/dev.sh`, `backend/tests/api/test_health.py`; **new:** `backend/tests/conftest.py`, `backend/tests/integration/__init__.py`.
- **DB impact:** test database only. **API impact:** none.
- **Integration:** A2 reuses the fixtures for worker integration tests (B2).
- **Tests:** existing 2 tests + a DB-connectivity test; run locally and in CI.
- **Acceptance:** `pytest -q` passes in Docker and CI with PostGIS; skipped tests show a reason. **Priority:** P0. **Output:** working test pipeline; first verified results in STATUS.md.

#### B1-A1-03 — Contract C-1: enums and Incident Record schemas (Phase 1A)
- **Implementation status:** C-1 v1 implemented on branch `feat/contract-c1-schemas` (not yet committed); current state and test result in `STATUS.md`. The acceptance line below says "signed off by A2 and A3": the project has one developer, who approved C-1 v1 acting in all roles (DECISIONS_LOG §3, C-1 notes). The original task text below is unchanged.
- **Purpose / behaviour:** Fix the shared vocabulary and the Incident Record shape (SRS Table 3.4) that all apps and agents use.
- **Approach:** `schemas/enums.py` with `str` Enums from D-005. `schemas/incident.py`: `IncidentSummaryOut` (queue cards), `IncidentDetailOut` (record + `ai_details`, `trust_signals`, `allocation_summary`, duplicate candidates, current recommendations, assignments), `LocationOut {lat, lon, text, source}`, `reference_no`. Matches SRS §7.2 field names; confidence 0–1 in the API, shown as % in the UI. Replace `ReportIn.channel` `mobile` with `app`.
- **Traceability:** SRS §3.3 Table 3.4, §7.2, NFR-S10 (NG911-style structure: time, type, source); SDS §2, §5.2 Table 5.2, §6.1; A-004.
- **Depends on:** D-004, D-005. **Files — modify:** `backend/app/schemas/report.py`; **new:** `backend/app/schemas/enums.py`, `backend/app/schemas/incident.py`, `backend/tests/fixtures/contracts/incident_detail.json`.
- **DB impact:** defines column vocabularies. **API impact:** defines response bodies.
- **Integration:** A2 and A3 review and sign off in DECISIONS_LOG C-1.
- **Tests:** schema unit tests validating the SRS §7.2 sample and the fixture.
- **Acceptance:** C-1 at v1, signed off by A2 and A3. **Priority:** P0. **Output:** schema modules + fixture.

#### B1-A1-04 — Contracts C-3 and C-4: auth shapes and API contract document (Phase 1A)
- **Implementation status:** implemented on branch `feat/contracts-c3-c4-api` (not yet committed); current state in `STATUS.md`. Differences from the text below, decided by the developer: `GET /health` stays unprefixed (approved D-006 text), so only the report test moved; the existing `POST /reports` stub now validates and returns 501 instead of a fake reference; an error-format module `backend/app/api/errors.py` was added; report endpoints stay in `reports.py`. "Contract approved by team" was met by the sole developer. The original task text below is unchanged.
- **Purpose / behaviour:** Publish every endpoint, its role and its request/response body before the frontend starts real integration.
- **Approach:** Write `docs/API_CONTRACT.md` from §4.3 (path, role, request, response, error codes 400/401/403/404/409/422/429/503, error body `{code, message, details}`). `schemas/auth.py` (`LoginIn`, `TokenOut`, `MeOut`, role enum). Add `/api/v1` prefix in `main.py` (D-006) and update the two existing tests. Register stub routers that return **501 Not Implemented** (never fake data) so OpenAPI shows the full surface.
- **Traceability:** SRS CI-1, UC-11, NFR-C2; SDS §4.1 API layer.
- **Depends on:** B1-A1-03, D-006, D-023. **Files — modify:** `backend/app/main.py`, `backend/tests/api/test_health.py`; **new:** `docs/API_CONTRACT.md`, `backend/app/schemas/auth.py`, `backend/app/api/routes/{auth,incidents,review,dispatch,driver,fleet,admin,analytics,intake_sim,routing}.py` (stubs).
- **DB impact:** none. **API impact:** full route surface (501 until implemented).
- **Integration:** A3 generates its TypeScript client from `/openapi.json`; A2 confirms routing proxy and reallocation semantics.
- **Tests:** test that every contracted path exists in OpenAPI with the right method; tests updated for prefix.
- **Acceptance:** contract approved by team; OpenAPI lists all paths. **Priority:** P0. **Output:** API_CONTRACT.md v1.

#### B1-A1-05 — Contracts C-5, C-6, C-7: events, pipeline interface, assignment payload (Phase 1A)
- **Implementation status:** implemented on branch `feat/contracts-c5-c6-c7` (not yet committed); current state in `STATUS.md`. Differences from the text below, decided by the developer (DECISIONS_LOG §3, C-5/C-6/C-7 notes): `save_trust` takes the assessment only; `claim_next` takes only `pending`/`reallocate`; `docs/API_CONTRACT.md` §4 lists the events and is checked by a test; tests were added (`test_events.py`, `test_assignment.py`, `test_pipeline_store_interface.py`) because the task asks for schema and signature tests. `FakePipelineStore` is not part of this task (A2 builds it). "Signed off by A2 and A3" was met by the sole developer. The original task text below is unchanged.
- **Purpose / behaviour:** Define exactly how the worker reads/writes data, how events reach clients and what the driver receives.
- **Approach:** `schemas/events.py` (envelope + one model per event in §4.4). `services/pipeline_store.py` **signatures and docstrings only in this task**: `claim_next(job_types) -> PipelineJob | None`, `save_transcript`, `save_location`, `save_triage(TriageResult)`, `save_trust(TrustAssessment, action)`, `find_duplicate_candidates(incident_id, distance_m, window_min) -> list[CandidateRow]`, `count_independent_nearby(incident_id, …)`, `get_caller_history(caller_id)`, `save_duplicate_results(...)`, `list_available_vehicles(types) -> list[VehicleRow]`, `save_recommendations(AllocationResult)`, `mark_stage_failed`, `mark_done`, `heartbeat(worker_id)`. Each write emits NOTIFY `incident_events` with `{event, incident_id}`. `schemas/assignment.py` (`DriverAssignmentOut`: incident type, severity, location, patients, ETA, route destination, hospital; allowed transitions table).
- **Traceability:** SDS §3.1, §3.2, §4.3, Table 6.3 (AgentOrchestrator, DispatchService); SRS CI-2; D-010.
- **Depends on:** B1-A1-03, B1-A2-01, D-010. **Files — modify:** `backend/app/ws/hub.py` (docstring correction only); **new:** `backend/app/schemas/events.py`, `backend/app/schemas/assignment.py`, `backend/app/services/pipeline_store.py` (interface).
- **DB / API impact:** none yet (interface).
- **Integration:** A2 builds `FakePipelineStore` against these signatures in `tests/unit/agents/fakes.py`.
- **Tests:** schema tests; signature/type check (`mypy` optional).
- **Acceptance:** C-5, C-6, C-7 signed off by A2 and A3. **Priority:** P0. **Output:** interface modules.

#### B1-A1-06 — Alembic (async) and PostGIS extension migration
- **Implementation status:** implemented on branch `feat/alembic-postgis` (not yet committed); current state in `STATUS.md`. Decided by the developer: `0001` downgrade drops PostGIS without CASCADE (refuses if anything depends on it); the local `dispatch` database was upgraded to `0001`. Found while doing it: the postgis/postgis image puts `tiger`/`topology` in the search path, so autogenerate saw the tiger tables; `env.py` now connects with `search_path = public` and a regression test covers it. Tests are in `backend/tests/integration/test_migrations.py` (throwaway database). The original task text below is unchanged.
- **Purpose / behaviour:** All schema changes go through migrations (README rule).
- **Approach:** `alembic init -t async` merged into existing `backend/migrations/`; `env.py` reads `DATABASE_URL`, imports `Base.metadata`, includes GeoAlchemy2 helpers so geometry types autogenerate correctly and the PostGIS internal tables are excluded. Revision `0001_enable_postgis`: `CREATE EXTENSION IF NOT EXISTS postgis`.
- **Traceability:** SDS §5 (PostgreSQL + PostGIS); SRS SW-4.
- **Depends on:** B1-A1-02. **Files — modify:** `backend/migrations/README.md`; **new:** `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_enable_postgis.py`.
- **DB impact:** extension only. **API impact:** none.
- **Tests:** `alembic upgrade head` then `downgrade base` on the test DB; `SELECT postgis_version()` test.
- **Acceptance:** upgrade/downgrade clean in Docker and CI. **Priority:** P0. **Output:** migration chain.

#### B1-A1-07 — Models: users, callers, user_sessions
- **Implementation status:** implemented together with B1-A1-07…11 on branch `feat/db-schema-v1` (one migration, `0002_initial_schema`); current state in `STATUS.md`; details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** Staff accounts (dispatcher, driver, admin), caller history for trust, and session rows for idle timeout and logout.
- **Approach:** `models/user.py`: `User` (SDS Table 5.4 + `failed_login_count`, `locked_until`, `on_duty`, `last_login_at`), unique `username`, role CHECK constraint; `UserSession` (D-023). `models/caller.py`: `Caller` (SDS Table 5.1), unique partial indexes on `phone_number` and `device_id` (when not null). Single `User` table with `role` (the SDS class hierarchy Dispatcher/Driver/Admin is behaviour, implemented in services).
- **Traceability:** SDS Tables 5.1, 5.4, §6.2; SRS UC-11, UC-03 1, NFR-C1, NFR-C4.
- **Depends on:** B1-A1-06, D-004, D-023. **Files — modify:** `backend/app/models/__init__.py`; **delete (with approval) or replace:** `backend/app/models/README.py` → content moved to `models/__init__.py` docstring; **new:** `backend/app/models/user.py`, `backend/app/models/caller.py`.
- **DB impact:** tables `users`, `callers`, `user_sessions`. **API impact:** none.
- **Tests:** constraint tests (duplicate username rejected, invalid role rejected).
- **Acceptance:** models import; autogenerate includes them. **Priority:** P0. **Output:** models.

#### B1-A1-08 — Models: incidents and incident_groups
- **Implementation status:** implemented together with B1-A1-07…11 on branch `feat/db-schema-v1` (one migration, `0002_initial_schema`); current state in `STATUS.md`; details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** The Incident Record table — the centre of the system.
- **Approach:** `models/incident.py`: `Incident` with SDS Table 5.2 columns plus D-004 columns (`reference_no`, `client_request_id`, `reporter_name`, `caller_gps`, `pipeline_*`, `ai_details` JSONB, `review_reasons` text[], `trust_signals` JSONB, `allocation_summary` JSONB, `settings_snapshot` JSONB, `created_at`, `updated_at`, `closed_at`). CHECK constraints for enums, `confidence` 0–1, `trust_score` 0–100. Indexes: GiST on `location`; btree on `(status, severity)`, `(incident_type, received_at)`, `pipeline_state` partial where pending/reallocate. `IncidentGroup` (SDS Table 5.3). `original_text` and `audio_ref` are never updated after insert (enforced in service + DB trigger raising on change).
- **Traceability:** SRS Table 3.4, UC-01 post-conditions, NFR-P12; SDS Tables 5.2, 5.3, §6.1.
- **Depends on:** B1-A1-07, D-004, D-005. **Files — new:** `backend/app/models/incident.py`.
- **DB impact:** `incidents`, `incident_groups`. **API impact:** none.
- **Tests:** insert/read geometry round-trip; constraint violations; original-text immutability trigger test.
- **Acceptance:** all columns present, constraints enforced. **Priority:** P0. **Output:** model.

#### B1-A1-09 — Models: vehicles, vehicle_locations, hospitals
- **Implementation status:** implemented together with B1-A1-07…11 on branch `feat/db-schema-v1` (one migration, `0002_initial_schema`); current state in `STATUS.md`; details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** Fleet, GPS history and hospitals used for allocation, tracking and transport.
- **Approach:** `models/fleet.py`: `Vehicle` (SDS Table 5.5; unique `plate_number`; unique `driver_id` when not null for the one-to-one link; GiST on `last_location`), `VehicleLocation` (Table 5.6; index `(vehicle_id, recorded_at desc)`), `Hospital` (Table 5.9; GiST on `location`).
- **Traceability:** SDS Tables 5.5, 5.6, 5.9; SRS UC-10, UC-12 3–4, TC-34.
- **Depends on:** B1-A1-07. **Files — new:** `backend/app/models/fleet.py`.
- **DB impact:** 3 tables. **API impact:** none.
- **Tests:** duplicate plate rejected; nearest-vehicle `ST_DWithin` query test.
- **Acceptance:** spatial queries use indexes (EXPLAIN recorded). **Priority:** P0. **Output:** model.

#### B1-A1-10 — Models: recommendations and assignments (double-dispatch guard)
- **Implementation status:** implemented together with B1-A1-07…11 on branch `feat/db-schema-v1` (one migration, `0002_initial_schema`); current state in `STATUS.md`; details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** Store ranked suggestions separately from approved assignments. Enforce "one open assignment per vehicle" in the database itself.
- **Approach:** `models/dispatch.py`: `Recommendation` (Table 5.7 + D-004 columns), `Assignment` (Table 5.8 + `decline_reason`, `declined_at`, `timed_out_at`, `notified_at`, `cancelled` status). Partial unique index `uq_assignment_open_vehicle ON assignments(vehicle_id) WHERE status IN ('approved','accepted')`. FK `approved_by` NOT NULL (every assignment has an approving dispatcher — NFR-S1).
- **Traceability:** SDS Tables 5.7, 5.8, §3.2; SRS NFR-S1, NFR-S6, UC-05/06 post-conditions.
- **Depends on:** B1-A1-08, B1-A1-09. **Files — new:** `backend/app/models/dispatch.py`.
- **DB impact:** 2 tables + partial unique index. **API impact:** none.
- **Tests:** second open assignment for the same vehicle raises IntegrityError; NULL `approved_by` rejected.
- **Acceptance:** guard proven by test. **Priority:** P0. **Output:** model.

#### B1-A1-11 — Models: audit_logs, settings, duplicate_candidates, confirmation_requests; initial schema migration
- **Implementation status:** implemented together with B1-A1-07…11 on branch `feat/db-schema-v1` (one migration, `0002_initial_schema`); current state in `STATUS.md`; details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** Complete the schema and apply it in one reviewed migration.
- **Approach:** `models/audit.py` `AuditLog` (Table 5.10; `details` JSONB rather than text so AI-suggested vs chosen vehicles are queryable — recorded in D-004). Trigger `audit_logs_no_modify` blocks UPDATE/DELETE (NFR-C10). `models/settings.py` `Setting` (Table 5.11). `models/review.py` `DuplicateCandidate`, `ConfirmationRequest` (D-004). Generate `0002_initial_schema`, review by hand (enum CHECKs, partial indexes, triggers), apply.
- **Traceability:** SDS Tables 5.10, 5.11, §2.2; SRS NFR-S9, NFR-C10, UC-04, UC-03 6, UC-12 5.
- **Depends on:** B1-A1-07…10, D-004. **Files — new:** `backend/app/models/audit.py`, `backend/app/models/settings.py`, `backend/app/models/review.py`, `backend/migrations/versions/0002_initial_schema.py`.
- **DB impact:** full schema. **API impact:** none.
- **Tests:** migration up/down; audit UPDATE/DELETE rejected; ERD relationships match SDS Table 2.2 (test enumerates FKs).
- **Acceptance:** `alembic upgrade head` creates every SDS table + approved additions; ERD diagram regenerated into `docs/diagrams/`. **Priority:** P0. **Output:** schema v1.

#### B1-A1-12 — Settings service with range validation and per-incident snapshot
- **Implementation status:** implemented on branch `feat/settings-audit-seed` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. Added: `update_many` (values that must change together, e.g. the duplicate weights) and settings for D-022, D-033, timers and a 40 km/h straight-line fallback speed (developer assumption). The original task text below is unchanged.
- **Purpose / behaviour:** Business-rule values are admin-configurable, validated and applied only to new incidents.
- **Approach:** `services/settings.py`: a typed registry of keys with default, type, min, max, description — `patients_per_ambulance` (1–6, 2), `dup_distance_m` (50–2000, 300), `dup_window_min` (1–120, 15), `dup_auto_link` (60–100, 85), `dup_possible` (30–95, 60), `triage_min_confidence` (0–100, 60), trust tier limits (high 70, medium 40), trust signal weights (Table 7.3.1), `rate_limit_*` (D-022), `assignment_timeout_s` 60, `signal_lost_s` 60, `geofence_m` 100, `fallback_speed_kmh`, `spare_vehicles` 2, duplicate weights (D-007). Cross-field rule: `dup_possible < dup_auto_link`. `get_snapshot()` returns all values for `incidents.settings_snapshot`. Seed migration inserts defaults. `core/config.py` defaults remain the bootstrap fallback only.
- **Traceability:** SRS UC-12 5/5a, Appendix C, §1.3 ("default values are settings"); SDS Table 5.11, §7.5; TC-36.
- **Depends on:** B1-A1-11. **Files — modify:** `backend/app/core/config.py` (comment: DB settings override); **new:** `backend/app/services/settings.py`, `backend/migrations/versions/0003_seed_settings.py`.
- **DB impact:** rows in `settings`. **API impact:** used by admin API (B1-A1-31).
- **Tests:** out-of-range rejected and old value kept (TC-36 at service level); snapshot contains all keys.
- **Acceptance:** every SRS default present and validated. **Priority:** P0. **Output:** service.

#### B1-A1-13 — Audit service
- **Implementation status:** implemented on branch `feat/settings-audit-seed` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** One function every service uses to record AI results, decisions and status changes with user and time.
- **Approach:** `services/audit.py` `record(session, action, user_id|None, incident_id|None, details: dict)` inside the caller's transaction (no audit = no commit). Action catalogue constant (`report.received`, `ai.triage`, `ai.trust`, `ai.duplicates`, `ai.allocation`, `incident.edited`, `duplicate.confirmed`, `review.decision`, `dispatch.approved`, `assignment.*`, `vehicle.locked/unlocked`, `settings.changed`, `user.*`, `auth.login_failed`, `auth.locked`).
- **Traceability:** SRS NFR-S9, UC-06 post-condition ("AI suggested, dispatcher chose, who and when"), UC-12 2/5; SDS Table 6.2 AuditLog.
- **Depends on:** B1-A1-11. **Files — new:** `backend/app/services/audit.py`.
- **DB impact:** inserts into `audit_logs`. **API impact:** none.
- **Tests:** rollback of the business change also rolls back the audit row and vice versa.
- **Acceptance:** used by every state-changing service (checked in review). **Priority:** P0. **Output:** service.

#### B1-A1-14 — Authentication service and endpoints
- **Implementation status:** implemented on branch `feat/auth-rbac` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. Refresh token = JWT of type `refresh` with the session id (no schema change), absolute lifetime 12 h (developer assumption); lockout/idle values come from the settings service. The original task text below is unchanged.
- **Purpose / behaviour:** Personal accounts, bcrypt hashes, JWT sessions, 5-failure lockout for 15 min, 30-min idle logout, logout ends session, drivers with an active assignment stay signed in.
- **Approach:** `core/security.py` (bcrypt hash/verify; JWT encode/decode with `jti`, `sub`, `role`, `exp`). `services/auth.py`: `login` (check `is_active`, `locked_until`; increment `failed_login_count`; lock at 5; reset on success; create `UserSession`), `refresh` (reject when `last_activity_at` > 30 min ago unless driver with open assignment; D-023), `logout` (revoke), `touch_session`. Routes in `api/routes/auth.py`. Same error message for unknown user and wrong password. Secret from `JWT_SECRET`; startup refuses the dev default outside `ENV=dev`.
- **Traceability:** SRS UC-11 (1, 1a, 1b, 3), NFR-C1, NFR-C4, NFR-C9; SDS Table 4.1 (JWT), §6.2; TC-32.
- **Depends on:** B1-A1-07, B1-A1-13, D-023. **Files — modify:** `backend/app/api/routes/auth.py` (stub → real), `backend/app/core/config.py`; **new:** `backend/app/core/security.py`, `backend/app/services/auth.py`, `backend/tests/api/test_auth.py`.
- **DB impact:** writes `users`, `user_sessions`, `audit_logs`. **API impact:** `/auth/login|refresh|logout|me`.
- **Integration:** A3 login screens (B1-A3-04, B1-A3-15).
- **Tests:** TC-32 (5 wrong → locked 15 min, correct password still refused while locked); idle 31 min → refresh 401; driver with open assignment → refresh allowed; logout → token rejected; disabled user refused.
- **Acceptance:** all tests pass. **Priority:** P0. **Output:** auth module.

#### B1-A1-15 — Role-based access control
- **Implementation status:** implemented on branch `feat/auth-rbac` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. The role matrix is `backend/tests/api/test_rbac_matrix.py` and is also checked against the Role column of `docs/API_CONTRACT.md`; simulator routes stay unprotected and 501 until D-014/B4-01. Response-field filtering (caller phone/location) is left to the tasks that build those responses. The original task text below is unchanged.
- **Purpose / behaviour:** Each role sees only what it needs; drivers only their own assignments; only admins manage users and settings.
- **Approach:** `api/deps.py`: `get_current_user` (validates token + session not revoked/idle, touches session), `require_roles(*roles)`, `require_driver_owns_assignment`. Role matrix in `docs/API_CONTRACT.md`. Caller phone/location only in dispatcher/admin responses.
- **Traceability:** SRS NFR-C2, NFR-C5; TC-48, TC-46.
- **Depends on:** B1-A1-14. **Files — new:** `backend/app/api/deps.py`, `backend/tests/api/test_rbac_matrix.py`.
- **DB / API impact:** guards on every private route.
- **Tests:** parametrised matrix: every private route × {anonymous, driver, dispatcher, admin} → expected 401/403/2xx; driver reading another driver's assignment → 403 (TC-48).
- **Acceptance:** matrix test covers 100 % of private routes in OpenAPI (test fails if a new route is unlisted). **Priority:** P0. **Output:** dependency module + matrix test.

#### B1-A1-16 — Intake service and `POST /reports` (save before processing)
- **Implementation status:** implemented on branch `feat/intake-pipeline-store` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. Decided by the developer: web/app only on this endpoint; a resend returns 200 with the same reference; the `incident.created` event waits for the WebSocket hub (B1-A1-29). The original task text below is unchanged.
- **C-1 v1 note (added 2026-11-20):** the response returns `reference_no` (string, e.g. `INC-000123`); `incident_id` stays an integer and is never the reference string. The current stub's `ReportOut.incident_id: str` is replaced in this task. The original task text below is unchanged.
- **Purpose / behaviour:** Turn a web/app text report into one Incident Record, commit it **before** any AI work, and return the reference number. Replaces the current stub.
- **Approach:** `services/intake.py` `create_report(ReportIn, channel, client_ip)` in one transaction: upsert `Caller` by phone/device; insert `Incident` with status `new`, `pipeline_state='pending'`, `location_source` = `gps` if lat/lon given, else `text` if address/landmark text given, else `unknown` with review reason `location_unknown`; store `caller_gps` separately; `settings_snapshot`; set `reference_no`; audit `report.received`; NOTIFY `report_pending`; commit; then emit `incident.created`. Idempotency: same `client_request_id` returns the existing reference (TC-04). Validation: description 1–2000 chars after trimming; phone pattern; name ≤ 100; free text stored as-is (Urdu/Sindhi accepted). Response: `{reference_no, status: "new", received_at}`. If the commit fails → 503, never a reference number. No geocoding or AI in the request path (D-011).
- **Traceability:** SRS UC-01 (1–5, 3a, 5a), F1, NFR-P12, NFR-C6, NFR-C9, §3.3; SDS §3.1 steps 1–6, Table 6.3 IntakeService; TC-01, TC-03, TC-04, TC-50.
- **Depends on:** B1-A1-11, B1-A1-12, B1-A1-13, D-011. **Files — modify:** `backend/app/api/routes/reports.py`, `backend/app/schemas/report.py`, `backend/tests/api/test_health.py` (move report test); **new:** `backend/app/services/intake.py`, `backend/tests/api/test_reports.py`.
- **DB impact:** writes `callers`, `incidents`, `audit_logs`. **API impact:** `POST /api/v1/reports` real.
- **Integration:** A3 public page and citizen app; A2 worker picks up `pending`.
- **Tests:** TC-01 (record exists, status new, reference returned); TC-03 (unknown location + reason); TC-04 (two posts with the same `client_request_id` → one row); TC-50 (`'; DROP TABLE incidents;--` saved verbatim, table intact); DB-down → 503 and no reference.
- **Acceptance:** record committed before response; no AI import in request path (asserted by test with the worker absent). **Priority:** P0. **Output:** intake service.

#### B1-A1-17 — Voice report upload and audio storage
- **Purpose / behaviour:** Accept a recorded voice report, keep the audio for review, and let the worker transcribe it.
- **Approach:** `POST /reports/voice` multipart: audio + same fields. Validate MIME/extension (WAV, MP3, M4A), size limit, duration ≤ 120 s (header probe; reject longer with 422). Store under `AUDIO_STORE_DIR` (git-ignored `audio_store/`, Docker volume) with a random file name; `audio_ref` = relative path; `original_text` empty until transcript (the transcript goes to `ai_details.transcript`; `original_text` gets the transcript once, written by the worker under the immutability rule "set once when empty"). `GET /incidents/{id}/audio` streams it to dispatchers only.
- **Traceability:** SRS UC-01 2a, CI-5, F1; SDS §4.2 Intake; TC-02 (storage half).
- **Depends on:** B1-A1-16. **Files — modify:** `backend/app/api/routes/reports.py`, `docker-compose.yml` (volume; shared file, CR), `.env.example` (CR); **new:** `backend/app/services/audio_store.py`, `backend/tests/api/test_voice_report.py`.
- **DB impact:** `incidents.audio_ref`. **API impact:** 2 endpoints.
- **Integration:** A2 STT reads `audio_ref` (B1-A2-04); A3 recorder (B1-A3-03/14).
- **Tests:** valid WAV accepted and saved before response; 3-min file rejected; wrong type rejected; driver cannot download audio.
- **Acceptance:** tests pass; file survives container restart. **Priority:** P1. **Output:** voice intake.

#### B1-A1-18 — Report flood protection (rate limiting)
- **Purpose / behaviour:** Stop floods of fake reports from one device or number without losing a real emergency.
- **Approach:** `services/rate_limit.py`: DB-based counter on recent `incidents` by `device_id`/`phone_number`/IP (no new infrastructure) using settings from D-022. Over the limit → 429 with a message telling the caller to also call 1122; the attempt is audited; the device is flagged (`callers.flagged_until`, added via D-004 if approved, otherwise derived) and the flag feeds trust signal "device flood −20".
- **Traceability:** SRS UC-01 5b, NFR-C8, Table 7.3.1; TC-05.
- **Depends on:** B1-A1-16, D-022. **Files — modify:** `backend/app/services/intake.py`; **new:** `backend/app/services/rate_limit.py`, `backend/tests/api/test_rate_limit.py`.
- **DB impact:** reads `incidents`; flag on `callers`. **API impact:** 429 on `/reports*`.
- **Tests:** TC-05 (10 reports in 1 minute → blocked after the limit, flag set); other devices unaffected.
- **Acceptance:** TC-05 passes. **Priority:** P1. **Output:** rate limiter.

#### B1-A1-19 — Pipeline persistence implementation (C-6) and NOTIFY
- **Implementation status:** implemented on branch `feat/intake-pipeline-store` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. `PostgresPipelineStore` is in `services/pipeline_store.py` (next to the protocol). Review reasons set here: low_confidence (incident's own snapshot), missing_info, location_unknown, ai_failed, low_trust → needs_check; possible_duplicate, low_trust_urgent, vehicle_shortage, transcript_unclear are warnings only. Available vehicles need an on-duty driver and GPS within `signal_lost_s`. `db/sql/duplicate_candidates.sql` was not created; the query lives in the store. The original task text below is unchanged.
- **Purpose / behaviour:** The real implementation the AI worker uses to claim jobs and save each stage, so AI results are stored safely and a crash never loses a report.
- **Approach:** Implement every `pipeline_store` function. `claim_next`: `UPDATE incidents SET pipeline_state='processing', pipeline_attempts=pipeline_attempts+1 … WHERE incident_id = (SELECT … WHERE pipeline_state IN ('pending','reallocate') ORDER BY severity-rank, received_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING …`. Stuck `processing` rows older than N minutes are reset to `pending` (crash recovery). Each `save_*` validates input with C-2 schemas, writes columns/JSONB, sets status (`triaged` / `needs_check`) and review reasons, writes audit `ai.*`, NOTIFYs. `find_duplicate_candidates`: same type, open, `ST_DWithin(location::geography, :pt, :d)`, `received_at` within window, excluding the incident itself and fakes. `list_available_vehicles`: `status='available'`, no open assignment, driver on duty, `last_seen_at` recent. `heartbeat` writes the worker heartbeat (settings row or small table, D-004 note).
- **Traceability:** SDS §3.1 steps 7–14, Table 6.3 AgentOrchestrator ("report never lost"); SRS NFR-P12, NFR-S9, UC-02 5, UC-04 1, UC-05 4–5.
- **Depends on:** B1-A1-05, B1-A1-11, B1-A1-13. **Files — modify:** `backend/app/services/pipeline_store.py`; **new:** `db/sql/duplicate_candidates.sql` (reference query), `backend/tests/integration/test_pipeline_store.py`.
- **DB impact:** reads/writes incidents, duplicate_candidates, recommendations, audit_logs. **API impact:** none.
- **Integration:** IP-1 with A2 (B2-01).
- **Tests:** two concurrent claimers never get the same incident; stale-processing recovery; candidate query respects 300 m / 15 min / same type / open; vehicles with open assignments excluded.
- **Acceptance:** all integration tests pass on PostGIS. **Priority:** P0. **Output:** persistence layer.

#### B1-A1-20 — Incident queue and detail APIs
- **Purpose / behaviour:** Give the dispatcher the severity-sorted queue and the full one-screen view.
- **Approach:** `services/incidents.py` + `api/routes/incidents.py`. Queue: open statuses, sort by severity rank then `received_at`; filters; pagination. Detail: record, original text/transcript, AI details with per-field confidence, trust score/tier/signals, review reasons, duplicate candidates, group info (report_count, "multiple reports"), current recommendations (batch), assignments, flags: `low_confidence`, `transcript_unclear`, `location_unknown`, `ai_failed`, `eta_approximate`, `vehicle_shortage`.
- **Traceability:** SRS UC-06 1, UC-02 1a/2a/4a, NFR-S2; SDS §7.2 items 1–6.
- **Depends on:** B1-A1-15, B1-A1-19. **Files — modify:** `backend/app/api/routes/incidents.py`; **new:** `backend/app/services/incidents.py`, `backend/tests/api/test_incidents.py`.
- **DB / API impact:** read-only `GET /incidents`, `GET /incidents/{id}`.
- **Tests:** ordering critical > high > medium > low; fields match fixture C-1; drivers refused.
- **Acceptance:** contract fixture validated against live response. **Priority:** P0. **Output:** query APIs.

#### B1-A1-21 — Incident edit and re-allocation trigger
- **Purpose / behaviour:** Dispatcher corrects type/severity/victims/location; the system saves the change and runs UC-05 again.
- **Approach:** `PATCH /incidents/{id}`: validate; keep the AI values in `ai_details` (never overwrite AI output — audit stores before/after); set `pipeline_state='reallocate'`; mark old recommendations `is_current=false`; audit `incident.edited`; NOTIFY. Location edit: dispatcher selects a map point (lat/lon) or text; `location_source` stays honest (`text` for dispatcher-entered text).
- **Traceability:** SRS UC-06 2; TC-23.
- **Depends on:** B1-A1-20. **Files — modify:** `backend/app/services/incidents.py`, `backend/app/api/routes/incidents.py`; **new:** `backend/tests/api/test_incident_edit.py`.
- **DB impact:** incidents, recommendations, audit. **API impact:** PATCH.
- **Integration:** IP-3 with A2 worker (B2-04).
- **Tests:** severity edit sets `reallocate` and audit has before/after; fake/closed incidents not editable (409).
- **Acceptance:** tests pass. **Priority:** P0. **Output:** edit API.

#### B1-A1-22 — Duplicate decision APIs and group merge
- **Purpose / behaviour:** Dispatcher confirms or rejects a possible duplicate; confirmed reports are linked in one group; rejected stay separate; decisions saved.
- **Approach:** `services/duplicates.py`: `confirm(candidate_id, user)` → create or reuse `IncidentGroup`, set `group_id` on both, update `report_count`, decision `confirmed`, audit; `reject` → decision `rejected`, both stay separate. Auto-linked candidates (≥ 85) are created by the worker through `pipeline_store` with decision `auto_linked` and can be **unlinked** by the dispatcher. Linking never closes, hides or changes the status of either incident (NFR-S4). The group's report count feeds the trust "independent reports" signal on re-evaluation.
- **Traceability:** SRS UC-04 4–5, 4a, post-conditions, NFR-S4; SDS Table 5.3; TC-13, TC-15.
- **Depends on:** B1-A1-19, B1-A1-20. **Files — modify:** `backend/app/api/routes/incidents.py` (or new `duplicates.py` router); **new:** `backend/app/services/duplicates.py`, `backend/tests/api/test_duplicates.py`.
- **DB impact:** incident_groups, incidents.group_id, duplicate_candidates, audit. **API impact:** confirm/reject (+ unlink).
- **Tests:** confirm links both; reject keeps apart; unanswered candidate leaves both dispatchable (TC-15); linked incidents both remain visible in the queue.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** duplicate service.

#### B1-A1-23 — Review queue and review decisions (Real / Fake / Need more information)
- **Purpose / behaviour:** Doubtful reports (low trust, low confidence, missing information, AI failure) are listed with reasons; the dispatcher decides; fake reports are closed and can never be dispatched; caller history updated.
- **Approach:** `services/review.py`: queue = incidents with `status='needs_check'` or open review reasons, sorted by severity; each item lists reasons. `decide(real)`: clear review reasons, status `triaged`, trigger allocation if not yet done (D-021), `callers.real_count += 1` (on confirmation as real). `decide(fake)`: status `fake`, `closed_at`, `callers.fake_count += 1`, cancel nothing else (no vehicle should exist; if an open assignment exists → 409 "dispatch already active, close the trip first"). `decide(need_info)`: stays in queue with reason `missing_info`. High/critical items are also in the normal queue with a warning (never only in the review queue).
- **Traceability:** SRS UC-07 1–3, 2a/2b, UC-03 6/6a and post-conditions; SDS §3.3; TC-24, TC-25, TC-09, TC-10.
- **Depends on:** B1-A1-20. **Files — modify:** `backend/app/api/routes/review.py`; **new:** `backend/app/services/review.py`, `backend/tests/api/test_review.py`.
- **DB impact:** incidents, callers, audit. **API impact:** `GET /review-queue`, `POST /incidents/{id}/review-decision`.
- **Tests:** TC-24 (fake → closed, no vehicle, fake_count +1); TC-25 (real → allocation requested); critical low-trust incident appears in the main queue flagged urgent (TC-10, API part).
- **Acceptance:** tests pass. **Priority:** P0. **Output:** review service.

#### B1-A1-24 — Caller confirmation requests (medium trust and dispatcher-initiated)
- **Purpose / behaviour:** Ask the caller to confirm by SMS or app while the record continues (medium trust), or when the dispatcher asks (UC-07 2). Show the answer when it arrives.
- **Approach:** `services/confirmation.py`: create `ConfirmationRequest` with a random token (stored hashed), send through `NotificationService` (SMS simulator or app link), show call-back number to the dispatcher. `POST /reports/{reference_no}/confirmation` (token) records `confirmed`/`denied`; inbound SMS "YES <ref>" via the simulator webhook. On confirm → trust re-evaluated (+ trust "confirmed" handled per UC-03 6b by setting a signal and requesting a trust recompute from A2 through `pipeline_state='reallocate'`-like job type `retrust`, defined in C-6). Never blocks or delays the incident.
- **Traceability:** SRS UC-03 6/6b, UC-07 2, Table 7.3.2 (medium tier); TC-12.
- **Depends on:** B1-A1-23, B1-A1-30. **Files — new:** `backend/app/services/confirmation.py`, `backend/app/api/routes/confirmation.py`, `backend/tests/api/test_confirmation.py`.
- **DB impact:** confirmation_requests, audit. **API impact:** 2 endpoints.
- **Tests:** TC-12 (medium trust → request sent, incident status unchanged and still in queue); valid token confirms; invalid token 404; second reply ignored.
- **Acceptance:** tests pass. **Priority:** P1. **Output:** confirmation flow.

#### B1-A1-25 — Dispatch approval service (locking, audit, conflicts)
- **Purpose / behaviour:** The only way a vehicle is sent. Requires an authenticated dispatcher, locks the chosen vehicles atomically, sets status `dispatched`, records AI suggestion vs dispatcher choice, informs drivers. Second dispatcher choosing a locked vehicle gets a warning and the next-best vehicle.
- **Approach:** `services/dispatch.py` `approve(incident_id, vehicle_ids, hospital_id, user)`: in one transaction `SELECT … FOR UPDATE` the incident (reject `fake`/`closed` → 409) and vehicles (ordered by id to avoid deadlocks); verify each vehicle `available` and no open assignment; insert `Assignment(status='approved', approved_by=user, approved_at=now)` per vehicle; vehicle `status='assigned'`; incident `status='dispatched'`; audit `dispatch.approved` with `{recommended:[…ranked ids], selected:[…], override_reason, manual_mode}`. The partial unique index is the last-line guard: IntegrityError → 409 `{code:"vehicle_locked", vehicle_id, next_best:[…]}` from current recommendations. After commit: `NotificationService.assignment_created` for each driver; WS `dispatch.approved`. Manual mode: allowed with vehicles chosen from `GET /vehicles` when no recommendation exists (`manual_mode=true`). High/critical incidents can be dispatched while trust/duplicate checks are pending (no precondition on those).
- **Traceability:** SRS UC-06 3–4, 3a, 4a, post-conditions, NFR-S1, NFR-S3, NFR-S6, NFR-S9, UC-07 2b; SDS §3.2 step 7, Table 6.3 DispatchService; TC-21, TC-22, TC-46.
- **Depends on:** B1-A1-10, B1-A1-13, B1-A1-15, B1-A1-20. **Files — modify:** `backend/app/api/routes/dispatch.py`; **new:** `backend/app/services/dispatch.py`, `backend/tests/api/test_dispatch.py`, `backend/tests/integration/test_dispatch_concurrency.py`.
- **DB impact:** assignments, vehicles, incidents, audit. **API impact:** `POST /incidents/{id}/dispatch`.
- **Tests:** TC-21 (locked, dispatched, audit has suggested vs chosen + approver); TC-22 (two concurrent approvals → exactly one succeeds, the other 409 with next best); TC-46 (no token / driver token → 401/403, no assignment rows); fake incident → 409; low-trust critical dispatchable.
- **Acceptance:** concurrency test runs 50 iterations with no double assignment. **Priority:** P0. **Output:** dispatch service.

#### B1-A1-26 — Assignment lifecycle (accept, decline, timeout, trip status, hospital change)
- **Purpose / behaviour:** Track each dispatched vehicle from approval to available, with timestamps; free vehicles on decline/timeout/completion.
- **Approach:** `services/assignments.py` state machine (C-7): `approved → accepted | declined | timed_out | cancelled`; `accepted → (on_scene) → (picked_up) → (at_hospital) → completed`. Accept → `accepted_at`, vehicle `en_route`. Decline (reason code) → vehicle `available`, dispatcher alert, `pipeline_state='reallocate'` for next vehicle (UC-08 2a). Timeout 60 s (scheduler, B1-A1-28) → `timed_out`, alert dispatcher (vehicle freed only when the dispatcher cancels or the driver declines; recorded under D-029 — "dispatcher can send another vehicle"). Status updates set `on_scene_at`, `picked_up_at`, `at_hospital_at`, `completed_at`; vehicle `on_scene/transporting/at_hospital/available`; incident `on_scene` on first arrival; incident `closed` when all its assignments are completed (or dispatcher closes). Hospital: suggested at dispatch from A2 (`allocation_summary.hospital`), dispatcher can change (UC-09 2a → WS to driver). Every transition audited.
- **Traceability:** SRS UC-08 2/2a/2b, UC-09 1–4, 1a, 2a, post-conditions, UC-12 3b; SDS Table 5.8, §3.2 steps 8–16; TC-26, TC-27, TC-28, TC-29.
- **Depends on:** B1-A1-25. **Files — modify:** `backend/app/api/routes/driver.py`, `backend/app/api/routes/dispatch.py`; **new:** `backend/app/services/assignments.py`, `backend/tests/api/test_assignments.py`.
- **DB impact:** assignments, vehicles, incidents, audit. **API impact:** driver accept/decline/status; dispatcher hospital/cancel.
- **Tests:** full happy path timestamps (TC-29 API part); decline frees vehicle + reallocate (TC-27); invalid transition (picked_up before accepted) → 409; driver acting on another driver's assignment → 403.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** lifecycle service.

#### B1-A1-27 — Driver duty and GPS ingestion
- **Purpose / behaviour:** GPS is accepted only while the driver is on duty; points arrive every ~5 s, possibly in late batches after a network drop; none are lost.
- **Approach:** `POST /driver/duty/start|end` set `users.on_duty`, vehicle `available`/`offline`; audit. `POST /driver/locations` accepts 1–500 points `{lat, lon, speed_kmh, recorded_at, client_point_id}`; rejects (403) when off duty; dedups by `client_point_id`; inserts `vehicle_locations`; updates `vehicles.last_location/last_seen_at` only if the point is newer; publishes `vehicle.position` for the newest point. End duty refused while an assignment is open (driver stays signed in — UC-11 1b).
- **Traceability:** SRS UC-11 2–3, UC-08 4, 3a, CI-2, CI-7, NFR-C5, NFR-P4; SDS Table 5.6, Table 6.3 TrackingService; TC-33, TC-41.
- **Depends on:** B1-A1-15, B1-A1-26. **Files — modify:** `backend/app/api/routes/driver.py`; **new:** `backend/app/services/tracking.py`, `backend/tests/api/test_driver_tracking.py`.
- **DB impact:** users.on_duty, vehicle_locations, vehicles. **API impact:** 3 endpoints.
- **Tests:** TC-33 (start → points accepted; end → 403); out-of-order batch keeps the newest last_location; duplicate points ignored.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** tracking ingestion.

#### B1-A1-28 — Scheduler: lost signal, assignment timeout, server-side geofence check
- **Purpose / behaviour:** Detect vehicles with no GPS for 60 s (grey "signal lost" + alert), assignments unanswered for 60 s, and arrival within 100 m when the app's auto-detection did not report it.
- **Approach:** `services/scheduler.py` asyncio loop started in the FastAPI lifespan (D-029), every 5 s: (1) on-duty vehicles with `last_seen_at` older than `signal_lost_s` → emit `vehicle.signal_lost` once, `signal_restored` when points resume; (2) `approved` assignments older than `assignment_timeout_s` → `timed_out` + alert; (3) accepted assignments whose last point is within `geofence_m` of the incident (or hospital) with no status yet → emit a `suggest_on_scene` event to the driver (the app or driver confirms; status is not forced by the server, to avoid false arrivals). Uses DB timestamps so a restart is safe.
- **Traceability:** SRS UC-10 1a, UC-08 2b, UC-09 1/1a/3; SDS Table 6.3 TrackingService; TC-28, TC-31.
- **Depends on:** B1-A1-26, B1-A1-27, B1-A1-29, D-029. **Files — modify:** `backend/app/main.py` (lifespan); **new:** `backend/app/services/scheduler.py`, `backend/tests/integration/test_scheduler.py`.
- **DB impact:** reads; assignment status writes. **API impact:** WS events only.
- **Tests:** frozen-clock tests for TC-28 and TC-31; no duplicate alerts per vehicle.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** scheduler.

#### B1-A1-29 — WebSocket hub and NOTIFY bridge
- **Purpose / behaviour:** Push live updates to dashboards and driver apps without reloading; carry worker events to clients.
- **Approach:** Replace `ws/hub.py` docstring with `ConnectionManager` (channels `dispatchers`, `driver:<id>`), `GET /api/v1/ws?token=` (JWT validated, role decides channels; driver may only join own channel). `ws/notify_listener.py`: asyncpg `LISTEN incident_events` → re-read the incident → publish the C-5 event. Heartbeat ping/pong every 20 s; clients re-sync with REST after reconnect (events are hints, REST is the truth).
- **Traceability:** SRS CI-2, NFR-P1, NFR-P4, NFR-P5; SDS §3.1 step 15, §4.3, Table 4.1 (WebSocket), Table 4.2 decision.
- **Depends on:** B1-A1-05, B1-A1-14. **Files — modify:** `backend/app/ws/hub.py`, `backend/app/main.py`; **new:** `backend/app/ws/notify_listener.py`, `backend/app/api/routes/ws.py`, `backend/tests/integration/test_ws.py`.
- **DB impact:** none (LISTEN). **API impact:** `/ws`.
- **Integration:** IP-2 (B2-02); A3 WS client (B1-A3-05).
- **Tests:** dispatcher receives `incident.created` after POST /reports; NOTIFY from a separate connection arrives as `incident.updated`; driver cannot subscribe to another driver; invalid token closes with 4401.
- **Acceptance:** event latency < 1 s locally (measured). **Priority:** P0. **Output:** real-time layer.

#### B1-A1-30 — Notification service (driver alert, SMS backup, caller SMS)
- **Purpose / behaviour:** Send assignment alerts to drivers and SMS to callers through replaceable adapters.
- **Approach:** `services/notification.py` interface `send_assignment(driver, payload)`, `send_sms(phone, text)`. Adapters: `WebSocketDriverAdapter` (primary), `FcmAdapter` (D-013, enabled only if credentials configured), `SimulatedSmsAdapter` (writes to `sms_outbox`/log, labelled SIMULATED, D-014). If the driver has no live WS connection and FCM fails → SMS backup + dispatcher alert (UC-06 4b). `assignments.notified_at` set.
- **Traceability:** SRS UC-06 4b, UC-08 1, CI-3, CI-4, SW-10, SW-11; SDS Table 6.3 NotificationService; TC-21 (alert part), TC-42.
- **Depends on:** B1-A1-29, D-013, D-014. **Files — new:** `backend/app/services/notification.py`, `backend/app/services/notification_adapters.py`, `backend/tests/unit/services/test_notification.py`.
- **DB impact:** `assignments.notified_at`. **API impact:** none.
- **Tests:** offline driver → SMS backup called and dispatcher alerted; FCM disabled when no credentials (no crash).
- **Acceptance:** tests pass. **Priority:** P0 (WS adapter), P1 (FCM). **Output:** notification service.

#### B1-A1-31 — Administration APIs
- **Purpose / behaviour:** Admin manages users, vehicles, hospitals and settings; every change validated and logged.
- **Approach:** `services/admin.py` + `api/routes/admin.py`. Users: create (temporary password, bcrypt), edit, disable (`is_active=false`), never hard-delete (audit FKs). Vehicles: unique plate (409, TC-34), link driver (one-to-one), delete blocked with open assignment (409, TC-35) and otherwise soft-disable if referenced. Hospitals: name, location point, departments, active. Settings: `PUT /admin/settings/{key}` through the settings service (422 + old value kept, TC-36). Audit-log viewer read-only with filters. Stations as text per D-026.
- **Traceability:** SRS UC-12 1–5, 3a, 3b, 5a, post-conditions; SDS §7.5, Tables 5.4, 5.5, 5.9, 5.11; TC-34, TC-35, TC-36, TC-48.
- **Depends on:** B1-A1-12, B1-A1-13, B1-A1-15. **Files — modify:** `backend/app/api/routes/admin.py`; **new:** `backend/app/services/admin.py`, `backend/app/schemas/admin.py`, `backend/tests/api/test_admin.py`.
- **DB impact:** users, vehicles, hospitals, settings, audit. **API impact:** admin endpoints.
- **Tests:** TC-34, TC-35, TC-36; non-admin refused (TC-48); settings change logged with admin id.
- **Acceptance:** tests pass. **Priority:** P1. **Output:** admin API.

#### B1-A1-32 — Analytics and export APIs (incident history and performance)
- **Purpose / behaviour:** Incident timeline and four performance measures, with CSV (and PDF) export.
- **Approach:** `services/analytics.py`: SQL in `db/sql/performance.sql`. Timeline per incident: received, triaged (audit `ai.triage`), approved, arrived (`on_scene_at`). Measures: triage accuracy (AI type/severity in `ai_details` vs final dispatcher value after edits), duplicate detection rate (auto/confirmed vs rejected candidates), ETA error (rank-1 `eta_seconds` vs actual `on_scene_at − accepted_at`), response time AI-assisted vs manual (`handled_mode`, D-025). Empty period → message (UC-13 2a); no manual data → AI-only series (3a). CSV via `csv` module; PDF is P2 (dependency needed → D-entry when started).
- **Traceability:** SRS UC-13 1–4, 2a, 3a, O8; SDS Table 8.3 measures; TC-37.
- **Depends on:** B1-A1-26. **Files — modify:** `backend/app/api/routes/analytics.py`; **new:** `backend/app/services/analytics.py`, `db/sql/performance.sql`, `backend/tests/api/test_analytics.py`.
- **DB impact:** read-only. **API impact:** analytics endpoints.
- **Tests:** seeded closed incidents produce known measures; TC-37 CSV columns; empty period message.
- **Acceptance:** tests pass. **Priority:** P1 (CSV), P2 (PDF). **Output:** analytics API.

#### B1-A1-33 — Health and service-status API (manual-mode signal)
- **Purpose / behaviour:** Tell the dashboard which services are down so it can show a warning and switch to manual mode.
- **Approach:** Extend `/health`: api, database, worker (heartbeat age < 30 s), osrm (`/route` probe with 1 s timeout), llm (gateway `ping` via worker heartbeat payload), geocoder. A monitor in the scheduler emits `system.service_status` on change. Response never fails because one dependency is down.
- **Traceability:** SRS NFR-S5, NFR-P13; TC-45.
- **Depends on:** B1-A1-28, B1-A1-29. **Files — modify:** `backend/app/api/routes/health.py`, `backend/tests/api/test_health.py`.
- **DB / API impact:** `/health` response extended (contract C-4 update).
- **Tests:** worker heartbeat stale → `worker: down`; OSRM unreachable → `osrm: down`, still 200.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** health API.

#### B1-A1-34 — Simulated seed data
- **Implementation status:** implemented on branch `feat/settings-audit-seed` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. Deviation: the seed lives in `backend/app/seed.py` and `backend/app/seed_data/*.json` (not `db/seed/`), so it runs and is tested inside the backend container; `db/README.md` points there. The original task text below is unchanged.
- **Purpose / behaviour:** Realistic but fictional users, stations, vehicles (30 → 100), hospitals (8) in the pilot area so every feature can be demonstrated.
- **Approach:** `db/seed/seed.py` (idempotent, `--size small|full`), data files in `db/seed/*.json`: admin/dispatcher/driver accounts (passwords from env, never committed), vehicles of each type with stations and positions on real pilot-area roads, hospitals with departments. Everything labelled SIMULATED.
- **Traceability:** SRS §1.4, NFR-C7, NFR-P6 (100 vehicles); SDS §8.1.
- **Depends on:** B1-A1-11. **Files — modify:** `db/README.md`; **new:** `db/seed/seed.py`, `db/seed/vehicles.json`, `db/seed/hospitals.json`, `db/seed/users.example.json`.
- **DB impact:** inserts simulated rows. **API impact:** none.
- **Tests:** seed twice → no duplicates; counts match.
- **Acceptance:** `python db/seed/seed.py --size full` on a fresh DB. **Priority:** P1. **Output:** seed data.

---

## Agent 2 — AI Agents and Intelligent Processing Development Agent

**Mission:** the AI pipeline and the three agents (Triage with trust scoring, Coordination, Resource
Allocation), the LangGraph orchestrator, the worker process, speech-to-text, geocoding, routing,
evaluation data and the evaluation harness. **AI never makes the final dispatch decision**, never
locks vehicles, and never marks a report fake.

**Pipeline overview (SDS §3.1, §3.3, Table 6.3):**
```
[API saved record, pipeline_state=pending] → worker claims (C-6)
  → stt (voice only) → geocode → triage (LLM, validated) → trust (rules) → policy (Table 7.3.2)
  → coordination (rules + similarity) → allocation (rules + OSRM) [skipped per D-021 for low-trust low/med]
  → save each stage (C-6) → NOTIFY → API → WebSocket → dashboard
Failure at any stage → retry (bounded) → mark_stage_failed → incident needs_check + ai_failed → manual mode
```

#### B1-A2-01 — Contract C-2: AI input/output schemas (Phase 1A)
- **Implementation status:** C-2 v1 implemented on branch `feat/contract-c2-ai-schemas` (not yet committed); current state and test result in `STATUS.md`. Differences from the text below (decided by the developer, DECISIONS_LOG §3 C-2 notes): `auto_linked` instead of `auto_link`; `route_geometry` instead of `route_polyline`; `hospital_suggestion` is `hospital_id`; tests are in `backend/tests/unit/agents/test_ai_schemas.py` as planned. "Signed off by A1 and A3" was met by the sole developer. The original task text below is unchanged.
- **Purpose / behaviour:** Fix exactly what each agent receives and returns so A1 can store it and A3 can display it, and so invalid model output can never drive dispatch.
- **Approach:** `schemas/ai.py` (Pydantic v2, `extra="forbid"`):
  - `TriageInput {incident_id, text, channel, language_hint?, caller_gps?, location_text?}`
  - `TriageResult {language, language_confidence, incident_type, type_confidence, severity, severity_confidence, victims_estimate: int|None, victims_confidence, location_words: str|None, has_real_details: bool, vague_or_joking: bool, missing_fields: list, overall_confidence 0–1, transcript_unclear: bool, model, prompt_version, latency_ms}` — `None` when unknown; location never guessed.
  - `GeocodeResult {lat, lon, source: gazetteer|nominatim|gps|unknown, matched_name, distance_to_gps_m?}`
  - `TrustAssessment {score 0–100, tier, signals: [{code, points, detail}], action: continue|continue_and_confirm|review_queue|urgent_with_warning}`
  - `DuplicateCandidateResult {candidate_incident_id, distance_m, time_diff_s, s_dist, s_time, s_meaning, match_confidence 0–100, decision: auto_link|possible|separate}`
  - `VehicleRecommendation {vehicle_id, vehicle_type, rank, eta_seconds, distance_meters, eta_is_approximate, is_spare, route_polyline?}`; `AllocationResult {needed: {type: count}, victims_unknown_check: bool, shortage: {type: available_count}|None, recommendations: [...], hospital_suggestion?, routing_mode: osrm|straight_line}`
  - JSON Schema export to `backend/tests/fixtures/contracts/ai/*.json` (by CR to A1's fixtures folder).
- **Traceability:** SRS Table 3.4, UC-02 4/5, UC-03 5, UC-04 3, UC-05 6, NFR-S2; SDS Table 6.3.
- **Depends on:** B1-A1-03. **Files — new:** `backend/app/schemas/ai.py`, `backend/tests/unit/agents/test_ai_schemas.py`.
- **DB / API impact:** defines JSONB contents and detail response fields.
- **Integration:** A1 storage (B1-A1-19), A3 display (B1-A3-07).
- **Tests:** valid/invalid examples; out-of-range confidence rejected; extra fields rejected.
- **Acceptance:** C-2 v1 signed off by A1 and A3. **Priority:** P0. **Output:** schema module + fixtures.

#### B1-A2-02 — LLM Gateway implementations
- **Implementation status:** implemented on branch `feat/triage-pipeline` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. Groq through `llm/openai_compatible.py` (`httpx`, no SDK) and Ollama; `FakeLLMClient` is for tests only and cannot be chosen by `LLM_PROVIDER` (so no running system uses made-up answers); D-008 provisional. Live call to Groq not verified (no key set when tested). The original task text below is unchanged.
- **Purpose / behaviour:** One interface so the model can be swapped by configuration only (SRS SW-3), with structured JSON output, temperature 0, timeouts and one retry on invalid JSON.
- **Approach:** Keep `LLMClient.complete_json`. Add `OllamaClient` (HTTP via `httpx`, already a dependency), `GroqClient` (HTTP to an OpenAI-compatible endpoint via `httpx` — avoids a new SDK; D-008), `FakeLLMClient` (deterministic fixtures keyed by input hash, for tests and offline demo). `get_llm_client()` from `settings.llm_provider`. Timeout (default 8 s to protect NFR-P1), JSON extraction, `LLMError`/`LLMTimeout` exceptions, latency and model name returned for audit. API key from env only; never logged.
- **Traceability:** SRS SW-3, §2.5 (free/open tools); SDS Table 4.1 Triage (language model through LangGraph).
- **Depends on:** D-008. **Files — modify:** `backend/app/llm/gateway.py`; **new:** `backend/app/llm/ollama.py`, `backend/app/llm/openai_compatible.py`, `backend/app/llm/fake.py`, `backend/tests/unit/agents/test_llm_gateway.py`.
- **DB / API impact:** none.
- **Tests:** mocked HTTP (httpx `MockTransport`): valid JSON, invalid JSON → `LLMError`, timeout → `LLMTimeout`; provider switch by env.
- **Acceptance:** tests pass without network. **Priority:** P0. **Output:** gateway.

#### B1-A2-03 — Triage Agent: prompt, parsing, validation, language detection
- **Implementation status:** implemented on branch `feat/triage-pipeline` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. The `low_confidence`/`missing_info` reasons are applied by C-6 `save_triage` from the agent's `missing_fields` and the incident's own `triage_min_confidence` (not duplicated in the agent). Accuracy with a live model is measured later (B1-A2-17). The original task text below is unchanged.
- **Purpose / behaviour:** Understand the report — language (Urdu, Sindhi, English, Roman-Urdu, mixed), incident type, severity, victims, location words, detail/vagueness flags — with a confidence for each result. Unknown → `null`, never guessed. Low confidence (< setting, default 60 %) or missing type/location → dispatcher must check.
- **Approach:** `agents/triage.py` `TriageAgent.run(TriageInput) -> TriageResult`. Versioned prompt in `agents/prompts/triage_v1.md` with few-shot simulated examples in English, Urdu script and Roman-Urdu; output must match the JSON Schema of `TriageResult`. Script-based pre-check (Arabic-script vs Latin) gives a language hint and a fallback when the model omits it. Validation: Pydantic; invalid → one retry with the error message appended; still invalid → raise `TriageFailed` (orchestrator marks needs_check, manual). Post-rules (deterministic, explained in `ai_details`): `overall_confidence < triage_min_confidence` → review reason `low_confidence`; missing type or location → `missing_info`. The LLM output never sets status or dispatch fields directly.
- **Traceability:** SRS UC-02 1–5, 1a, 2a, 4a, F2, NFR-P1, NFR-P7, NFR-P8, NFR-S2; SDS Table 4.1, Table 6.3 TriageAgent; TC-06, TC-07, TC-08.
- **Depends on:** B1-A2-01, B1-A2-02. **Files — modify:** `backend/app/agents/triage.py`; **new:** `backend/app/agents/prompts/triage_v1.md`, `backend/tests/unit/agents/test_triage.py`.
- **DB / API impact:** none directly (stored through C-6).
- **Tests (FakeLLMClient):** TC-06 sample → accident/high/victims > 1/confidence present; TC-07 → `missing_info`; TC-08 → `low_confidence`; invalid JSON twice → `TriageFailed`; Urdu-script input gets `ur` language.
- **Acceptance:** unit tests pass; live-model accuracy is measured later in B1-A2-17/B8. **Priority:** P0. **Output:** Triage Agent.

#### B1-A2-04 — Speech-to-text integration (Whisper / faster-whisper)
- **Purpose / behaviour:** Turn a voice report into text and a detected language; flag unclear transcripts; keep the audio.
- **Approach:** `integrations/stt.py` `SpeechToText.transcribe(path) -> {text, language, avg_logprob, no_speech_prob, duration_s}` using faster-whisper (model size by setting; `small` default for CPU, D-entry for the dependency). Model loaded once per worker. `transcript_unclear = avg_logprob < threshold or no_speech_prob > threshold` (thresholds calibrated in B8). Transcript written once to `original_text` (empty before) and to `ai_details.transcript`. If STT fails → incident `needs_check` with reason `stt_failed`; dispatcher can play the audio (manual).
- **Traceability:** SRS UC-01 2a, UC-02 1/1a, SW-2, CI-5, NFR-P2; SDS Table 4.1 Intake (Whisper); TC-02, TC-39.
- **Depends on:** B1-A2-01; dependency approval (faster-whisper). **Files — modify:** `backend/requirements.txt` (CR); **new:** `backend/app/integrations/__init__.py`, `backend/app/integrations/stt.py`, `backend/tests/unit/agents/test_stt.py`, `db/eval_data/voice/README.md` (list of simulated clips, not committed if large).
- **DB / API impact:** none directly.
- **Tests:** interface tested with a stub model; one short English WAV fixture through the real model marked `@pytest.mark.slow`.
- **Acceptance:** 60-s clip transcribed on the demo machine within the NFR-P2 budget (time recorded). **Priority:** P1. **Output:** STT module.

#### B1-A2-05 — Geocoding: pilot gazetteer + Nominatim fallback
- **Purpose / behaviour:** Turn location words into a map point; compare with the caller's GPS; never invent a location.
- **Approach:** `infra/gazetteer/landmarks.csv` (50–100 simulated pilot-area landmarks: name, aliases EN/Urdu/Roman-Urdu, lat, lon). `integrations/geocoding.py`: normalise text → exact/alias match → fuzzy match (stdlib `difflib`) with score threshold → Nominatim (rate-limited 1 req/s, timeout 2 s, `countrycodes=pk`, viewbox = pilot area) → else `unknown`. If caller GPS present and text unresolved → use GPS with `source=gps`. Compute `distance_to_gps_m` for trust. Results cached.
- **Traceability:** SRS UC-01 3/3a, UC-02 3, SW-6, Table 7.3.1 GPS signals; SDS Table 4.1 (Nominatim); D-009; TC-03, TC-11.
- **Depends on:** B1-A2-01, D-009. **Files — modify:** `infra/gazetteer/README.md`; **new:** `infra/gazetteer/landmarks.csv`, `backend/app/integrations/geocoding.py`, `backend/tests/unit/agents/test_geocoding.py`.
- **DB / API impact:** none directly.
- **Tests:** alias match (Roman-Urdu), fuzzy threshold, Nominatim mocked down → `unknown`, GPS distance computed.
- **Acceptance:** tests pass offline. **Priority:** P0. **Output:** geocoder + gazetteer data.

#### B1-A2-06 — TrustScorer (deterministic rules)
- **Implementation status:** complete, merged into `main` via PR #15 (`8437bcc`); current state in `STATUS.md`; details in CHANGES.md. `TrustScorer.assess(inputs, severity, settings)` returns the C-2 `TrustAssessment` including the Table 7.3.2 action; D-035 handled with an `ai_unavailable` reason. Not included: a points value for the caller-confirmation result, which is not in SRS Table 7.3.1. The original task text below is unchanged.
- **Purpose / behaviour:** Compute the trust score and tier exactly per SRS Table 7.3.1 with a reason for every point, so likely fake reports are caught without AI guessing.
- **Approach:** `agents/trust.py` `TrustScorer.score(inputs, settings) -> TrustAssessment`. Inputs: caller history (`real_count`, `fake_count`), `distance_to_gps_m`, independent nearby count (C-6 `count_independent_nearby`: distinct callers/devices, same type, within duplicate distance/window), `has_real_details`, `vague_or_joking`, device flood flag, confirmation result. Start 50; +15 real history; −30 per fake (floor −60); +15 GPS ≤ 500 m; −20 GPS > 2 km; +15 / +25 nearby; +10 details; −15 vague; −20 flood; clamp 0–100; tiers from settings. No history → neutral (UC-03 1a). Weights from `settings_snapshot`. Low LLM confidence is **not** an input.
- **Traceability:** SRS UC-03 1–5, 1a, 6b, F3, Appendix C Table 7.3.1; SDS Table 6.3 (TriageAgent calculates trust); D-012; TC-09, TC-11.
- **Depends on:** B1-A2-01, D-012. **Files — modify:** `backend/app/agents/trust.py`; **new:** `backend/tests/unit/agents/test_trust.py`.
- **DB / API impact:** none directly.
- **Tests:** one test per signal, the floor at −60, clamping, tier boundaries 39/40/69/70, TC-09 (two fakes → low), TC-11 (−20 for > 2 km).
- **Acceptance:** 100 % branch coverage of `trust.py`. **Priority:** P0. **Output:** TrustScorer.

#### B1-A2-07 — Trust × severity action policy (urgent never waits)
- **Implementation status:** complete, merged into `main` via PR #15 (`8437bcc`); current state in `STATUS.md`; details in CHANGES.md. Unknown severity is treated as urgent (never held back). `allocate_now(action)` implements D-021. The original task text below is unchanged.
- **Purpose / behaviour:** Decide what happens next from tier and severity exactly per Table 7.3.2, guaranteeing high/critical reports are never held.
- **Approach:** Pure function `agents/policy.py` `decide_action(tier, severity) -> action` + `review_reasons`. High tier → continue. Medium → continue (+ confirmation request; at once for high/critical). Low + low/medium → `review_queue`. Low + high/critical → `urgent_with_warning` (incident stays in main queue, allocation runs, dispatch allowed). Missing/low-confidence flags from triage add review reasons but never block high/critical.
- **Traceability:** SRS Table 7.3.2, UC-03 6/6a, NFR-S3; SDS §3.3; TC-10, TC-12.
- **Depends on:** B1-A2-06. **Files — new:** `backend/app/agents/policy.py`, `backend/tests/unit/agents/test_policy.py`.
- **Tests:** full 3 × 4 truth table; property test: severity in {high, critical} ⇒ action ≠ `review_queue`.
- **Acceptance:** truth table passes. **Priority:** P0. **Output:** policy function.

#### B1-A2-08 — Text similarity component (backup duplicate signal)
- **Purpose / behaviour:** Score how alike two report descriptions are, as the "meaning" signal for duplicates.
- **Approach:** `agents/similarity.py` interface `similarity(a, b) -> 0..1` with implementation per D-007: multilingual sentence-transformer if approved (embeddings cached per incident in memory/JSONB), else character n-gram TF-IDF cosine with stdlib/numpy-free code. Normalisation of Urdu/Roman-Urdu spelling variants.
- **Traceability:** SRS UC-04 2; SDS Table 4.1 (rules + text similarity); D-007.
- **Depends on:** D-007. **Files — new:** `backend/app/agents/similarity.py`, `backend/tests/unit/agents/test_similarity.py`.
- **Tests:** identical > paraphrase > unrelated ordering on fixed examples; symmetric; empty text → 0.
- **Acceptance:** tests pass. **Priority:** P1. **Output:** similarity module.

#### B1-A2-09 — Coordination Agent (duplicate detection)
- **Purpose / behaviour:** Compare a new triaged report with open incidents; auto-link only at very high confidence; ask the dispatcher at medium confidence; keep separate otherwise. Never hide a separate emergency.
- **Approach:** `agents/coordination.py` `CoordinationAgent.run(incident, candidates, settings) -> list[DuplicateCandidateResult]`. Candidates come from C-6 `find_duplicate_candidates` (same type, ≤ distance, ≤ window, open). Score per D-007 (configurable weights). Decision: ≥ `dup_auto_link` → `auto_link`; ≥ `dup_possible` → `possible`; else `separate`. Only the best auto-link candidate links (no chain-merging of groups by AI). Results saved via C-6; auto-links create group links but **never change either incident's status** and are reversible by the dispatcher.
- **Traceability:** SRS UC-04 1–4, 4a, F4, Table 7.3.4, NFR-S4, NFR-P9; SDS Table 4.1, Table 6.3 CoordinationAgent; TC-13, TC-14, TC-15.
- **Depends on:** B1-A2-01, B1-A2-08, B1-A1-05 (interface). **Files — modify:** `backend/app/agents/coordination.py`; **new:** `backend/tests/unit/agents/test_coordination.py`.
- **Tests:** TC-13 (100 m, 5 min, same fire text → auto_link); TC-14 (2 km → not a candidate); boundary 84.9 vs 85.0; different type never compared.
- **Acceptance:** tests pass with FakePipelineStore. **Priority:** P0. **Output:** Coordination Agent.

#### B1-A2-10 — Routing service (OSRM) with straight-line fallback; OSRM pilot-area setup
- **Purpose / behaviour:** Real road routes, distances and ETAs; when OSRM is down, straight-line distance with ETA clearly marked approximate.
- **Approach:** `infra/osrm/` scripts: download pilot-area extract (Sindh/Sukkur) from Geofabrik, `osrm-extract/partition/customize` with the car profile, `osrm` service in compose (CR, B7 finalises). `integrations/routing.py` `RoutingService`: `table(sources, dest)` for many vehicles at once (one OSRM `/table` call, keeps NFR-P3), `route(from, to)` with geometry + steps for previews and driver navigation, timeout 1.5 s. Fallback: haversine × road factor (setting) / `fallback_speed_kmh` → `eta_is_approximate=True`, `routing_mode=straight_line`.
- **Traceability:** SRS UC-05 4, 5a, SW-5, CI-6, NFR-P3, NFR-P10, NFR-S5; SDS Table 4.1 Routing, Table 6.3 RoutingService, §4.5 osrm; TC-20, TC-40.
- **Depends on:** B1-A2-01. **Files — modify:** `infra/osrm/README.md`; **new:** `infra/osrm/prepare.sh`, `backend/app/integrations/routing.py`, `backend/tests/unit/agents/test_routing.py`.
- **DB / API impact:** none directly.
- **Tests:** mocked OSRM table/route parsing; OSRM down → approximate flag set (TC-20 unit level).
- **Acceptance:** the README sample route returns from the local OSRM container (recorded). **Priority:** P0. **Output:** routing module + OSRM data recipe.

#### B1-A2-11 — Resource Allocation Agent
- **Implementation status:** complete, merged into `main` via PR #15 (`8437bcc`); current state in `STATUS.md`; details in CHANGES.md. Depends on B1-A2-10 (OSRM), which is not built: the agent takes an `EtaProvider`; until OSRM exists `StraightLineEta` (straight line at `fallback_speed_kmh`, approximate) is used. No hospital suggestion (B1-A2-12, D-018 open). The original task text below is unchanged.
- **Purpose / behaviour:** Decide vehicle types and counts, rank free vehicles by ETA, keep needed + 2 spare, warn about shortage, flag uncertain victim counts. Never locks a vehicle.
- **Approach:** `agents/resource.py` `ResourceAllocationAgent.run(incident, vehicles, settings) -> AllocationResult`. Rules (Table 7.3.3, D-019): accident with injuries → ambulances = max(1, ceil(victims / patients_per_ambulance)) (+1 backup if critical); fire → ≥ 1 fire truck + ambulances by the same rule + backup; medical → ambulances (≥ 1); other → no type, nearest available of all types, dispatcher chooses; victims unknown → 1 vehicle + `victims_unknown_check`. Vehicles from C-6 `list_available_vehicles` (excludes locked/open assignments). Rank per type by OSRM `table` ETA; list = needed + `spare_vehicles`; `is_spare` marked; shortage when available < needed. Fixed deterministic tie-break (distance, then vehicle_id).
- **Traceability:** SRS UC-05 1–6, 3a, 4a, 5a, post-conditions ("no vehicle locked"), F5, Table 7.3.3, NFR-P3; SDS Table 4.1, Table 6.3; TC-16, TC-17, TC-18, TC-19, TC-20.
- **Depends on:** B1-A2-10, B1-A1-05, D-019. **Files — modify:** `backend/app/agents/resource.py`; **new:** `backend/tests/unit/agents/test_resource.py`.
- **Tests:** TC-16 (6 victims → 3 ambulances + 2 spare = 5 listed); TC-17 (unknown → 1 + check); TC-18 (fire → truck + ambulances + backup); TC-19 (shortage count); locked vehicles never appear; agent code has no write access to vehicles (asserted by using a read-only fake).
- **Acceptance:** tests pass. **Priority:** P0. **Output:** Resource Allocation Agent.

#### B1-A2-12 — Hospital suggestion
- **Purpose / behaviour:** Suggest a hospital for transport that the driver confirms and the dispatcher can change.
- **Approach:** `agents/hospital.py` `suggest(incident, hospitals, routing)` per D-018 (department match, nearest by ETA, active only); stored in `allocation_summary.hospital_suggestion`.
- **Traceability:** SRS UC-09 2, 2a; SDS Table 5.9; D-018.
- **Depends on:** B1-A2-10, D-018. **Files — new:** `backend/app/agents/hospital.py`, `backend/tests/unit/agents/test_hospital.py`.
- **Tests:** department match beats closer non-matching; inactive excluded; none active → `None` with warning.
- **Acceptance:** tests pass. **Priority:** P1. **Output:** helper.

#### B1-A2-13 — LangGraph orchestrator
- **Implementation status:** implemented on branch `feat/triage-pipeline` (not yet committed; `langgraph==1.2.24`, CR-003); current state in `STATUS.md`; details in CHANGES.md. Stages not built yet are skipped openly: STT (voice without text → `speech_to_text` failed, manual), geocoding (caller GPS only until B1-A2-05/D-009), coordination (until B1-A2-08/09). After a Triage failure the Trust Scorer still runs (D-035), so the plan's "later stages not run" applies to coordination and allocation only. The original task text below is unchanged.
- **Purpose / behaviour:** Run the stages in the right order with typed state, per-stage persistence, bounded retries and failure handling so a report is never lost.
- **Approach:** `agents/orchestrator.py` builds a LangGraph `StateGraph` (dependency approval) with nodes `stt → geocode → triage → trust_policy → coordination → allocation` and conditional edges: skip `stt` for text; skip `allocation` for `review_queue` action (D-021) unless severity high/critical; separate small graphs for jobs `reallocate` (allocation only) and `retrust` (trust_policy only). Each node writes through C-6 immediately (partial results survive later failures). Errors: transient (timeout, connection) → retry up to 2 with backoff; permanent (validation) → `mark_stage_failed` → incident `needs_check` + `ai_failed` reason → manual mode. Per-stage timing logged (for NFR-P1/P3).
- **Traceability:** SDS §3.1 steps 7–14, §4.2 (Agent orchestrator — LangGraph), Table 6.3 AgentOrchestrator; SRS NFR-P12, NFR-S5, NFR-S3; TC-44.
- **Depends on:** B1-A2-03…12. **Files — new:** `backend/app/agents/orchestrator.py`, `backend/tests/unit/agents/test_orchestrator.py`.
- **Tests (FakeLLM + FakePipelineStore + mocked OSRM):** text happy path order; voice path includes STT; triage failure → needs_check, later stages not run, original record untouched; low-trust low-severity skips allocation; critical low-trust still allocates; OSRM down → approximate result saved.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** orchestrator.

#### B1-A2-14 — AI worker process
- **Implementation status:** implemented on branch `feat/triage-pipeline` (not yet committed); current state in `STATUS.md`; details in CHANGES.md. Claims only `pending` jobs (`reallocate` comes with B1-A2-15). Not yet a service in `docker-compose.yml` (shared file; planned for B2-01). The original task text below is unchanged.
- **Purpose / behaviour:** A separate long-running process that picks up pending reports immediately, runs the orchestrator, reports its health and shuts down cleanly.
- **Approach:** Replace `workers/ai_worker.py` docstring: async main loop — `LISTEN report_pending` with a 2-s polling fallback; `claim_next` (C-6); run graph; heartbeat every 10 s (includes LLM/STT readiness); configurable concurrency (default 2); SIGTERM → finish current job then exit; structured logs with incident id. `python -m app.workers.ai_worker`.
- **Traceability:** SDS §4.5 (ai-engine container), §3.1; SRS NFR-P1, NFR-P6, NFR-P12; D-010.
- **Depends on:** B1-A2-13, B1-A1-05. **Files — modify:** `backend/app/workers/ai_worker.py`; **new:** `backend/tests/unit/agents/test_worker_loop.py`.
- **DB / API impact:** through C-6 only.
- **Tests:** loop processes N fake jobs then idles; crash mid-job leaves state recoverable (with A1's stale-reset); SIGTERM handling.
- **Acceptance:** tests pass; joined to real DB in B2-01. **Priority:** P0. **Output:** worker.

#### B1-A2-15 — Re-allocation and re-trust jobs; route function for the driver proxy
- **Purpose / behaviour:** Recompute recommendations after dispatcher edits, driver declines or a Real decision; recompute trust after caller confirmation; give the API a route function for driver navigation.
- **Approach:** Worker handles `pipeline_state='reallocate'` (allocation graph; new `batch_no`, old batch kept for audit) and `retrust`. `integrations/routing.py` exposes `route()` that A1's `/routing/route` endpoint calls (A1 owns the router, A2 owns the function — IP-4).
- **Traceability:** SRS UC-06 2, UC-08 2a, UC-07 3, UC-03 6b, UC-08 3; NFR-P3; TC-23, TC-27, TC-25.
- **Depends on:** B1-A2-13, B1-A2-14. **Files — modify:** `backend/app/agents/orchestrator.py`, `backend/app/workers/ai_worker.py`; **new:** `backend/tests/unit/agents/test_reallocate.py`.
- **Tests:** declined vehicle excluded from new batch; edited severity changes counts; confirmation raises trust.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** job handlers.

#### B1-A2-16 — Simulated evaluation datasets
- **Purpose / behaviour:** Labelled, fictional data to measure triage, duplicate detection, STT and ETA against the SRS targets.
- **Approach:** `db/eval_data/reports.jsonl` (≥ 200 reports: EN, Urdu script, Roman-Urdu, Sindhi; labels type, severity, victims, location landmark), `duplicate_groups.jsonl` (≥ 50 groups incl. near-miss non-duplicates), `voice/manifest.csv` (team-recorded simulated clips with reference transcripts), `eta_routes.csv` (origin/destination pairs). Labelling guide + double-labelling of 20 % to check agreement.
- **Traceability:** SRS NFR-P7–P10, O8, §2.6 (datasets); SDS §8.4 Table 8.3.
- **Depends on:** none (content). **Files — modify:** `db/README.md`; **new:** files above + `db/eval_data/LABELLING_GUIDE.md`.
- **Tests:** schema check script validates every line.
- **Acceptance:** sizes met; no real personal data (reviewed). **Priority:** P1. **Output:** datasets.

#### B1-A2-17 — Evaluation harness and LLM provider selection
- **Purpose / behaviour:** Measure each agent against targets and choose the default LLM (D-008) on evidence.
- **Approach:** `backend/tests/ai_eval/run_eval.py`: type accuracy, severity accuracy, confusion matrices, latency p50/p95, duplicate recall and false-merge rate, WER per language, ETA error (with simulator in B8). Outputs a Markdown report into `docs/test-reports/ai_eval_<date>.md`. Run for each candidate provider/model.
- **Traceability:** SRS NFR-P7, P8, P9, P10, P1, P2; SDS Table 8.3.
- **Depends on:** B1-A2-03, 04, 09, 16. **Files — new:** `backend/tests/ai_eval/run_eval.py`, `backend/tests/ai_eval/metrics.py`, `backend/tests/ai_eval/test_metrics.py`.
- **Tests:** metric functions unit-tested on tiny known inputs.
- **Acceptance:** first evaluation report produced; D-008 decision proposed with numbers. **Priority:** P1. **Output:** harness + report.

---

## Agent 3 — Frontend, Mobile Applications and User Experience Development Agent

**Mission:** every user-facing screen in SDS §7: public report page, dispatcher dashboard (queue,
incident review, dispatch approval, review queue, live map, reports), admin panel, and the Android app
(citizen and driver modes). Uses only contracted APIs (C-3, C-4, C-7) and AI shapes (C-2). AI results
are always presented as **recommendations**, with confidence and trust visible, and dispatch always
requires an explicit dispatcher action.

**Proposed structure** (existing `frontend/dashboard` and `frontend/pwa` hold only `.gitkeep`;
`mobile/` is new pending D-002):
```
frontend/dashboard/   React + TS + Vite — dispatcher + admin (+ dev Channel Simulator page, SIMULATED)
frontend/pwa/         React + TS + Vite — public web report page (rename to public-report if approved)
frontend/shared/      (proposed) generated API client, types, severity/trust UI components, i18n
mobile/               (proposed, D-002) React Native Android app — citizen mode + driver mode
```

#### B1-A3-01 — Web scaffolding and typed API client
- **Implementation status:** implemented on branch `feat/frontend-foundation` (not yet committed), 2026-11-22, as group F1 with B1-A3-02. npm workspace `frontend/{shared,dashboard,pwa}`; types generated from the running API (`npm run gen:api`, drift check `npm run gen:api:check`); client with auth header, one shared refresh on 401, session end, `{code, message, details}` mapping, 503 hook, timeout. No mock mode was built: the screens built so far use only endpoints that already work. Stack decision D-015. Details in CHANGES.md. The original task text below is unchanged.
- **Purpose / behaviour:** Create the two Vite React apps and a shared client generated from the backend OpenAPI so the UI cannot drift from the contract.
- **Approach:** Follow `frontend/README.md` (Vite `react-ts`) for `dashboard` and `pwa`; `frontend/shared` package with `openapi-typescript`-generated types and a thin fetch wrapper (auth header, refresh on 401, error body `{code, message}` mapping, 503 → service warning). `VITE_API_URL`. A mock mode serving only the contract fixtures, with a visible "MOCK DATA" banner, until the real endpoint passes its tests. Linting and the test runner per D-015.
- **Traceability:** SRS SW-8, NFR-P17, NFR-P18; SDS Table 4.1.
- **Depends on:** B1-A1-04 (OpenAPI), D-015. **Files — modify:** `frontend/README.md`; **delete:** `frontend/dashboard/.gitkeep`, `frontend/pwa/.gitkeep` (as README instructs); **new:** Vite projects, `frontend/shared/**`.
- **DB / API impact:** none (consumer).
- **Tests:** client unit tests (refresh flow, error mapping); `npm run build` for both apps.
- **Acceptance:** both apps build; types regenerate from a running API with one command. **Priority:** P0. **Output:** scaffolds.

#### B1-A3-02 — Shared UI rules: severity, trust, confidence, warnings, bilingual text
- **Implementation status:** implemented on branch `feat/frontend-foundation` (not yet committed), 2026-11-22, with B1-A3-01. Components in `frontend/shared/src/ui/` (`badges.tsx`, `states.tsx`, `ui.css`) and English/Urdu text in `frontend/shared/src/i18n/` (not `frontend/shared/ui/*` as written below; the workspace keeps sources under `src/`). Added `CallNotice` (safety rule 10). The original task text below is unchanged.
- **Purpose / behaviour:** Apply SDS §7.6 consistently: same colours everywhere, confidence with every AI result, trust tier on every report, service-unavailable warnings, English/Urdu text.
- **Approach:** Components: `SeverityBadge` (red critical, orange high, blue medium, green low, plus text/icon so colour is not the only cue), `TrustBadge` (tier + score), `ConfidenceMeter` (percentage + "dispatcher must check" below threshold), `AiRecommendationLabel` ("AI recommendation — dispatcher decides"), `ServiceStatusBanner` (from `system.service_status`), `ApproximateEtaTag`, `EmptyState`, `LoadingState`, `ErrorState`. i18n with EN/UR resource files and RTL support for Urdu on public/citizen screens; Sindhi accepted as free text.
- **Traceability:** SRS NFR-S2, NFR-P16, NFR-S5; SDS §7.6, §7.2.
- **Depends on:** B1-A3-01. **Files — new:** `frontend/shared/ui/*`, `frontend/shared/i18n/{en,ur}.json`.
- **Tests:** component tests: colours per severity, threshold label, RTL direction for `ur`.
- **Acceptance:** components used by all screens (review checklist). **Priority:** P0. **Output:** UI kit.

#### B1-A3-03 — Public web report page
- **Purpose / behaviour:** Anyone can report without calling: notice "If life is in danger, also call 1122", description or voice recording, GPS or typed address/landmark, optional name/phone, Send → reference number.
- **Approach:** Single mobile-first page (`frontend/pwa`). GPS via `navigator.geolocation` (refusal → prompt for landmark; none → still sendable, location unknown). Voice via `MediaRecorder` (max 2 min, preview, re-record) → `POST /reports/voice`; text → `POST /reports`. `client_request_id` generated per submission (safe retry). Validation messages; 429 message; 503 message with the 1122 notice; success screen with the reference number. EN/UR toggle. Only the fields NFR-C6 allows.
- **Traceability:** SRS UC-01 1–5, 2a, 3a, 5b, NFR-S7, NFR-C6, NFR-P16; SDS §7.1; TC-01, TC-03, TC-47.
- **Depends on:** B1-A3-02, B1-A1-16/17 (real) or mocks. **Files — new:** `frontend/pwa/src/pages/ReportPage.tsx` and components.
- **Tests:** form validation; GPS denied path; recorder stops at 120 s; notice always visible (TC-47); submit success/429/503 states.
- **Acceptance:** works at 360 px width in Chrome/Edge/Firefox. **Priority:** P0. **Output:** public page.

#### B1-A3-04 — Dashboard authentication and role routing
- **Purpose / behaviour:** Dispatcher and admin log in, land on their role's home, are signed out after 30 min idle, and can log out.
- **Approach:** Login form (`/auth/login`), lockout message, token kept in memory with refresh; idle timer warning at 28 min; route guards by role (dispatcher: queue/map/review/reports; admin: admin panel + reports).
- **Traceability:** SRS UC-11 1, 1a, 1b, 3, NFR-C2, NFR-C4; TC-32.
- **Depends on:** B1-A3-01, B1-A1-14. **Files — new:** `frontend/dashboard/src/auth/*`, `frontend/dashboard/src/pages/LoginPage.tsx`.
- **Tests:** guard redirects; lockout message; idle logout with fake timers.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** auth UI.

#### B1-A3-05 — WebSocket client and live data store
- **Purpose / behaviour:** Keep queue, incident detail and map current without reloading.
- **Approach:** One WS connection per session (C-5), auto-reconnect with backoff, re-fetch via REST on reconnect, event → store updates (TanStack Query cache invalidation or a small store), connection indicator.
- **Traceability:** SRS CI-2, NFR-P1, NFR-P4; SDS §3.1 step 15.
- **Depends on:** B1-A3-01, C-5. **Files — new:** `frontend/shared/ws/*`.
- **Tests:** mock socket: events update the store; reconnect triggers re-fetch.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** WS client.

#### B1-A3-06 — Incident queue
- **Purpose / behaviour:** Severity-sorted list of incidents; each card shows severity colour, location, time, trust tier and flags (urgent-with-warning, possible duplicate, multiple reports, low confidence, AI failed).
- **Approach:** `GET /incidents` + live events; sound/visual cue for new critical items; filters; empty and loading states.
- **Traceability:** SRS UC-06 1, NFR-S2; SDS §7.2 item 1.
- **Depends on:** B1-A3-02, B1-A3-05, B1-A1-20. **Files — new:** `frontend/dashboard/src/pages/QueuePage.tsx`, components.
- **Tests:** ordering; new event inserts card in the right place; flags render.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** queue screen.

#### B1-A3-07 — Incident review screen
- **Purpose / behaviour:** One screen with everything the dispatcher needs: original report exactly as sent (and audio player + transcript with "unclear" warning), AI-extracted type/severity/victims/location each with confidence, trust tier + score + reasons, review reasons, duplicate warning with Confirm / Keep separate, map of the location, edit details.
- **Approach:** `GET /incidents/{id}`; edit form → `PATCH` (shows "recalculating recommendations…" until `recommendation.ready`); duplicate actions → confirm/reject endpoints; "Mark as fake" sends to the review decision flow with confirmation dialog. AI values and dispatcher-edited values shown distinctly.
- **Traceability:** SRS UC-06 1–2, UC-02 1a/2a/4a, UC-03 6a, UC-04 4–5, NFR-S2; SDS §7.2 items 2–5, 7; TC-08, TC-10, TC-13, TC-23.
- **Depends on:** B1-A3-06, B1-A1-21, B1-A1-22, C-2. **Files — new:** `frontend/dashboard/src/pages/IncidentPage.tsx`, `components/incident/*`.
- **Tests:** each warning renders for its flag; edit triggers PATCH; duplicate confirm/reject calls.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** review screen.

#### B1-A3-08 — Dispatch approval panel
- **Purpose / behaviour:** Ranked vehicles with ETA (and "approximate" tag), route preview, shortage warning, select/deselect or pick others manually, short summary, explicit **Approve Dispatch**; ≤ 3 clicks for a recommended dispatch.
- **Approach:** Needed vehicles pre-selected (spares unselected); route lines on map; Approve → summary dialog → Confirm (open incident = click 1, Approve = 2, Confirm = 3). 409 `vehicle_locked` → warning + next-best offered. Manual mode (no recommendations or AI down): list of available vehicles nearest-first from `GET /vehicles` with a "manual dispatch" label. Hospital suggestion shown, changeable.
- **Traceability:** SRS UC-06 3–4, 3a, 4a, UC-05 4a/5a, NFR-P14, NFR-S1, NFR-P13; SDS §7.2 items 6–7; TC-19, TC-20, TC-21, TC-22, TC-51.
- **Depends on:** B1-A3-07, B1-A1-25. **Files — new:** `frontend/dashboard/src/components/dispatch/*`.
- **Tests:** click count = 3; 409 path; approximate tag; manual mode list; nothing is sent without Confirm.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** approval panel.

#### B1-A3-09 — Review queue screen
- **Purpose / behaviour:** Doubtful reports with the reason for each; ask the caller to confirm (send request / show call-back number); see the reply; decide Real, Fake or Need more information.
- **Approach:** `GET /review-queue`; actions call confirmation-request and review-decision endpoints; Fake requires a confirmation dialog; high/critical items show "dispatch allowed while checking" with a link to the approval panel.
- **Traceability:** SRS UC-07 1–3, 2a, 2b; SDS §3.3; TC-09, TC-24, TC-25.
- **Depends on:** B1-A3-02, B1-A1-23, B1-A1-24. **Files — new:** `frontend/dashboard/src/pages/ReviewQueuePage.tsx`.
- **Tests:** reasons render; decisions call API; reply appears via event.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** review queue UI.

#### B1-A3-10 — Live fleet map
- **Purpose / behaviour:** All vehicles coloured by status, signal-lost in grey at last position, active incidents, hospitals, routes of en-route vehicles (dashed), filters by type/status/area, vehicle detail panel (driver, status, speed, incident, ETA), alerts.
- **Approach:** Leaflet + OSM tiles (attribution, D-028); initial `GET /fleet/live`, then `vehicle.position` / `signal_lost` events; marker updates without full re-render (100 vehicles at 5-s rate).
- **Traceability:** SRS UC-10 1–3, 1a, F7, NFR-P4; SDS §7.3; TC-30, TC-31, TC-41.
- **Depends on:** B1-A3-05, B1-A1-27, B1-A1-28. **Files — new:** `frontend/dashboard/src/pages/LiveMapPage.tsx`, `components/map/*`.
- **Tests:** status colour mapping; grey on signal_lost; filter logic; render 100 markers within budget (perf test).
- **Acceptance:** tests pass. **Priority:** P0. **Output:** live map.

#### B1-A3-11 — Admin panel
- **Purpose / behaviour:** Users, Vehicles, Hospitals, Settings, Audit Log menus; add/edit/disable; settings form with ranges and "applies to new incidents only".
- **Approach:** CRUD screens on `/admin/*`; inline server validation errors (duplicate plate, active-assignment delete block, out-of-range setting); hospital location picked on a map; audit log read-only table with filters.
- **Traceability:** SRS UC-12 1–5, 3a, 3b, 5a; SDS §7.5; TC-34, TC-35, TC-36.
- **Depends on:** B1-A3-04, B1-A1-31. **Files — new:** `frontend/dashboard/src/pages/admin/*`.
- **Tests:** error rendering per TC; non-admin cannot reach routes.
- **Acceptance:** tests pass. **Priority:** P1. **Output:** admin UI.

#### B1-A3-12 — Reports and performance screens
- **Purpose / behaviour:** Filters (period, type, status), incident list with timeline (received → triaged → approved → arrived), performance page with the four measures, Export.
- **Approach:** `/analytics/*`; charts via a light chart library (dependency per D-entry) or plain SVG; "no data" and "AI-assisted only" states.
- **Traceability:** SRS UC-13 1–4, 2a, 3a; TC-37.
- **Depends on:** B1-A3-04, B1-A1-32. **Files — new:** `frontend/dashboard/src/pages/reports/*`.
- **Tests:** empty states; export triggers download.
- **Acceptance:** tests pass. **Priority:** P1. **Output:** reports UI.

#### B1-A3-13 — Mobile app scaffolding (Android)
- **Purpose / behaviour:** One Android app with citizen mode (no login) and driver mode (login), offline storage, generated API client.
- **Approach:** Per D-002 (recommended React Native in `mobile/`): navigation, secure token storage, shared types copied/generated from OpenAPI, persistent offline queue (reports and GPS points), permission flows, debug network config for the local CA (D-024).
- **Traceability:** SRS SW-9, §2.4 (Android 9+), CI-7, NFR-P17; SDS Table 4.1 Mobile app.
- **Depends on:** D-002, B1-A1-04. **Files — new:** `mobile/**` (proposed).
- **Tests:** build an APK; unit tests for the offline queue.
- **Acceptance:** debug APK installs on Android 9+ device/emulator. **Priority:** P0. **Output:** app skeleton.

#### B1-A3-14 — Citizen report mode (with offline queue)
- **Purpose / behaviour:** Same report flow as the web page, plus: stored locally when offline and sent once when the network returns; SMS option shown.
- **Approach:** Form + GPS + voice recording (≤ 2 min) + optional name/phone; `client_request_id` saved with the queued report; background retry on connectivity change; "sent / waiting for network" states; EN/UR.
- **Traceability:** SRS UC-01 1–5, 5a, CI-7, NFR-S7, NFR-P16; SDS §7.1; TC-04, TC-47.
- **Depends on:** B1-A3-13, B1-A1-16/17. **Files — new:** `mobile/src/citizen/*`.
- **Tests:** offline → queued → online → exactly one POST (with same id).
- **Acceptance:** TC-04 passes on device. **Priority:** P1. **Output:** citizen mode.

#### B1-A3-15 — Driver login, duty and GPS sharing
- **Purpose / behaviour:** Driver logs in, taps Start Duty to begin sharing GPS every ~5 s, End Duty to stop; GPS never sent off duty; points buffered during network loss.
- **Approach:** Large-button screen; foreground location service while on duty only; batch upload `POST /driver/locations`; End Duty disabled during an open assignment.
- **Traceability:** SRS UC-11 2–3, UC-08 4, 3a, NFR-C5, NFR-S8, CI-7; SDS §7.4; TC-33.
- **Depends on:** B1-A3-13, B1-A1-27. **Files — new:** `mobile/src/driver/duty/*`.
- **Tests:** no location calls when off duty (unit, mocked location API); buffered points flushed in order.
- **Acceptance:** TC-33 on device. **Priority:** P0. **Output:** duty module.

#### B1-A3-16 — Driver assignment alert, Accept / Cannot Go
- **Purpose / behaviour:** Red banner and sound alert; summary (severity, type, place, patients, ETA); map with route preview; two big buttons; reason picker for Cannot Go (no typing); 60-s countdown.
- **Approach:** `assignment.new` via WS (and FCM when configured); accept/decline endpoints; "new information" banner on `assignment.updated` (UC-08 4a).
- **Traceability:** SRS UC-08 1, 2, 2a, 2b, 4a, NFR-S8, NFR-P5; SDS §7.4 items 1–4; TC-26, TC-27, TC-28, TC-42.
- **Depends on:** B1-A3-15, B1-A1-26, B1-A1-30. **Files — new:** `mobile/src/driver/assignment/*`.
- **Tests:** UI state machine tests; reason codes only.
- **Acceptance:** tests pass. **Priority:** P0. **Output:** assignment screen.

#### B1-A3-17 — Driver navigation
- **Purpose / behaviour:** On Accept, navigation opens immediately from the vehicle's position to the incident (and later to the hospital) with no typing, recalculates when off route, works with cached map area on weak network, voice guidance.
- **Approach:** Per D-016: in-app map with OSRM route via `GET /routing/route`, step list and text-to-speech prompts, off-route detection (> 50 m from the polyline for 3 fixes → re-request), pre-cached pilot-area tiles; one-tap fallback to the external navigation app.
- **Traceability:** SRS UC-08 3, 3a, NFR-P15, NFR-S8; SDS §3.2 steps 10–12, §7.4 item 5; TC-26.
- **Depends on:** B1-A3-16, B1-A2-10/15 (route function), D-016. **Files — new:** `mobile/src/driver/navigation/*`.
- **Tests:** off-route detection unit tests; route request on accept.
- **Acceptance:** navigation opens with zero typing on device. **Priority:** P0. **Output:** navigation.

#### B1-A3-18 — Driver trip status
- **Purpose / behaviour:** Automatic "on scene" within 100 m and "at hospital" on arrival; manual Patient Picked Up (opens hospital navigation) and Available; manual On Scene fallback; hospital change from dispatcher shown.
- **Approach:** Client geofence on location updates (radius from settings in the assignment payload); status calls with `source=auto|manual`; one large "next step" button (SDS §7.4 item 7).
- **Traceability:** SRS UC-09 1–4, 1a, 2a, post-conditions; SDS §7.4 items 6–7; TC-29.
- **Depends on:** B1-A3-17, B1-A1-26. **Files — new:** `mobile/src/driver/trip/*`.
- **Tests:** geofence unit tests (99 m vs 101 m); status sequence.
- **Acceptance:** TC-29 with simulated movement (full run in B3). **Priority:** P0. **Output:** trip module.

#### B1-A3-19 — Frontend test suites and mobile checklist
- **Purpose / behaviour:** Repeatable tests for web screens and a written device checklist for the app (SDS §8.1).
- **Approach:** Jest/RTL (or Vitest per D-015) suites in CI for both web apps; `docs/test-reports/mobile_checklist.md` mapping TC-26…TC-33, TC-04, TC-47 to manual steps on Android 9+.
- **Traceability:** SDS §8.1; SRS NFR-P17.
- **Depends on:** B1-A3-03…18. **Files — modify:** `.github/workflows/ci.yml` (CR to A1); **new:** test files, checklist.
- **Acceptance:** CI runs web tests; checklist complete. **Priority:** P1. **Output:** test suites.

---

## Batch 1 completion evidence
- Test reports per agent in `docs/test-reports/batch1_<agent>.md` (commands, pass/fail counts).
- Contracts C-1…C-7 at v1 in DECISIONS_LOG.
- STATUS.md updated per task; CHANGES.md entries per task.

---

# BATCH 2 — End-to-end report pipeline integration

**Objective:** a report submitted on the web page appears on the dispatcher dashboard, triaged, trust-checked, duplicate-checked and with vehicle recommendations, within the NFR-P1 budget, with no mocks in the path.
**Agents:** A1 + A2 lead, A3 consumes. **Prerequisites:** Batch 1 Phase 1A–1C tasks for intake, pipeline store, WS, orchestrator, worker, queue/review screens.

#### B2-01 — Join worker to the real database (IP-1)
- **Agents:** A2 (worker), A1 (pipeline_store). **Purpose:** replace `FakePipelineStore` with the real one in integration tests; add the `ai-worker` service to compose (same image, `python -m app.workers.ai_worker`, CR on shared file).
- **Traceability:** SDS §4.5; SRS NFR-P12. **Files:** `docker-compose.yml`, `backend/tests/integration/test_pipeline_e2e.py` (new).
- **Tests / acceptance:** POST /reports → worker → incident `triaged` with ai_details, trust, candidates, recommendations in DB, using FakeLLM and a local OSRM. **Priority:** P0.

#### B2-02 — Worker events to the dashboard (IP-2)
- **Agents:** A1, A2, A3. **Purpose:** NOTIFY → hub → `incident.updated` / `recommendation.ready` → queue and review screen update live.
- **Traceability:** SDS §3.1 step 15; SRS CI-2, NFR-P1. **Files:** none new beyond tests (`test_ws_pipeline.py`); A3 removes mock mode for these screens.
- **Acceptance:** report-to-dashboard latency measured on 20 text reports with the chosen LLM, p95 recorded (target ≤ 10 s, verified formally in B8). **Priority:** P0.

#### B2-03 — Replace frontend mocks with live APIs (IP-5, intake to review)
- **Agents:** A3 (A1 support). **Purpose:** public page, queue, incident review, review queue use real endpoints; MOCK banner gone for these screens.
- **Acceptance:** TC-01, TC-03, TC-06, TC-07, TC-08 executed through the UI and recorded. **Priority:** P0.

#### B2-04 — Re-allocation round trip (IP-3)
- **Agents:** A1, A2, A3. **Purpose:** dispatcher edits severity → new recommendations appear (TC-23); Real decision on doubtful report → allocation (TC-25).
- **Acceptance:** TC-23, TC-25 pass end-to-end; NFR-P3 time recorded. **Priority:** P0.

#### B2-05 — Trust and duplicate scenarios end-to-end
- **Agents:** A2 lead, A1, A3. **Purpose:** run TC-09 … TC-15 with seeded caller histories and paired reports through the full stack.
- **Acceptance:** all seven TCs pass; urgent low-trust critical report visible in the main queue immediately (TC-10). **Priority:** P0.

#### B2-06 — AI failure and manual fallback in the pipeline
- **Agents:** A2, A1, A3. **Purpose:** stop the worker or LLM mid-flow; report still saved (TC-44); incident flagged `ai_failed`; dashboard banner; dispatcher can open the incident and dispatch manually.
- **Acceptance:** TC-44 passes; manual dispatch possible with AI down. **Priority:** P0.

---

# BATCH 3 — Dispatch, driver and live-tracking workflow

**Objective:** complete loop from approval to vehicle available again, on the dashboard and the Android app.
**Agents:** A1 + A3 lead, A2 for routing/reallocation. **Prerequisites:** Batch 2 done; B1-A1-25…30, B1-A3-08, 10, 13–18.

#### B3-01 — Approve → driver alert (TC-21, TC-42)
- **Agents:** A1, A3. Dispatch approval from the panel creates assignments, locks vehicles, alerts the driver app via WS/FCM within 5 s; audit shows AI suggestion vs choice and approver.
- **Acceptance:** TC-21 and TC-42 recorded with timings. **Priority:** P0.

#### B3-02 — Concurrent approval and double-dispatch protection (TC-22)
- **Agents:** A1, A3. Two dashboard sessions approve the same vehicle; one wins, the other sees the warning and next best.
- **Acceptance:** TC-22 through the UI; DB shows one open assignment per vehicle. **Priority:** P0.

#### B3-03 — Accept, navigation, live GPS (TC-26, TC-30, TC-41) (IP-4)
- **Agents:** A3, A1, A2. Driver accepts, navigation opens without typing via `/routing/route`, GPS every 5 s, map updates within 5 s, ETA on dashboard.
- **Acceptance:** TCs recorded on a real Android device. **Priority:** P0.

#### B3-04 — Decline, timeout and reallocation (TC-27, TC-28)
- **Agents:** A1, A2, A3. Cannot Go frees the vehicle and new recommendations appear; no answer for 60 s alerts the dispatcher.
- **Acceptance:** both TCs pass. **Priority:** P0.

#### B3-05 — Trip status to completion (TC-29) and lost signal (TC-31)
- **Agents:** A3, A1. Auto on-scene / at-hospital, manual picked-up / available, hospital change by dispatcher, times saved, vehicle unlocked; GPS stopped 60 s → grey + alert.
- **Acceptance:** TC-29, TC-31 pass with a simulated drive (B4-03 simulator or device). **Priority:** P0.

#### B3-06 — Driver app unavailable → SMS backup (UC-06 4b)
- **Agents:** A1, A3. Driver offline at approval → dispatcher notified and SMS (simulated) sent.
- **Acceptance:** scenario recorded. **Priority:** P1.

---

# BATCH 4 — Simulated external services, channels and scenarios

**Objective:** every input channel and the fleet are realistically simulated so the system can be demonstrated and load-tested without real services.
**Agents:** A1 + A2 lead, A3 for simulator UI. **Prerequisites:** Batch 2; B1-A1-17/24/30, B1-A2-04.

#### B4-01 — SMS channel simulator (D-014)
- **Agents:** A1. `POST /intake/sms` webhook (shared secret), inbound SMS → Incident Record (`channel='sms'`), outbound confirmation/acknowledgement SMS logged in the simulator outbox; "YES <ref>" replies confirm. `db/simulators/sms_simulator.py` CLI. Labelled SIMULATED.
- **Traceability:** SRS UC-01 (SMS), CI-4, SW-11, UC-03 6. **Acceptance:** SMS report reaches the dashboard; confirmation round trip (TC-12) via SMS. **Priority:** P1.

#### B4-02 — Voice channel simulator and STT end-to-end (TC-02, TC-39 preview)
- **Agents:** A1, A2. `POST /intake/voice` + simulator script sending clips from `db/eval_data/voice/`; transcript + audio visible on the dashboard; unclear-transcript warning.
- **Acceptance:** TC-02 passes with an Urdu clip. **Priority:** P1.

#### B4-03 — Vehicle movement simulator (100 vehicles)
- **Agents:** A2 (routes) + A1 (driver API usage). `db/simulators/vehicle_simulator.py`: logs in simulated drivers, starts duty, follows OSRM routes at realistic speed, sends GPS every 5 s, accepts assignments and reports statuses automatically; option to drop signal. Used for TC-29/30/31, NFR-P6, NFR-P10 (ETA error = predicted vs simulated travel time).
- **Acceptance:** 100 simulated vehicles run for 30 min without errors. **Priority:** P0.

#### B4-04 — Channel simulator page (dashboard, SIMULATED)
- **Agents:** A3. Developer page to send SMS/voice/web reports and run prepared scenarios; hidden behind the admin role and a feature flag.
- **Acceptance:** usable in demo. **Priority:** P2.

#### B4-05 — Scenario library
- **Agents:** A2, A1. `db/simulators/scenarios/*.yaml`: bus accident with 6 victims, fire with duplicate callers, fake-call flood (TC-05), low-trust critical, OSRM-down, shortage of vehicles. One command runs a scenario end-to-end.
- **Acceptance:** every scenario runs and its expected outcome is asserted. **Priority:** P1.

---

# BATCH 5 — Administration, reporting and performance analytics integration

**Objective:** UC-12 and UC-13 work end-to-end; the manual baseline is collected for O8.
**Agents:** A1 + A3. **Prerequisites:** B1-A1-31/32, B1-A3-11/12, Batch 3 (closed incidents exist).

#### B5-01 — Admin panel end-to-end (TC-34, TC-35, TC-36, TC-48)
- Users/vehicles/hospitals/settings via UI; settings change applies only to new incidents (verified by comparing `settings_snapshot` of incidents before/after). **Priority:** P1.

#### B5-02 — Incident history and performance reports (TC-37)
- Timeline accuracy against audit timestamps; four measures computed from scenario runs; CSV export opens correctly; PDF if approved. **Priority:** P1.

#### B5-03 — Manual baseline sessions (D-025)
- Timed dispatcher sessions in manual mode with the same scenarios; results stored and shown as the comparison series. **Priority:** P1.

#### B5-04 — Audit completeness check
- Script verifies every AI result, decision and status change in scenario runs has an audit row with user/time; audit rows cannot be modified (NFR-S9, NFR-C10). **Priority:** P0.

---

# BATCH 6 — Manual mode, resilience and safety validation

**Objective:** prove every safety requirement with evidence.
**Agents:** all (A1 lead for the matrix). **Prerequisites:** Batches 2–5.

| Task | Content | Evidence |
|---|---|---|
| B6-01 Safety requirement matrix | Map NFR-S1…S10 to automated tests and scenarios | `docs/test-reports/safety_matrix.md` |
| B6-02 AI + OSRM outage (TC-45) | Stop worker/LLM and OSRM; warning visible; manual dispatch completes; approximate ETA labelled | TC-45 recorded |
| B6-03 Unapproved dispatch attempts (TC-46) | Direct API calls without approval/role; no assignment created | TC-46 recorded |
| B6-04 Urgent-never-waits (NFR-S3) | Critical low-trust and critical possible-duplicate reports are dispatchable immediately | scenario logs |
| B6-05 Careful merging (NFR-S4) | Medium matches unanswered stay separate; auto-link reversible | TC-13–15 rerun |
| B6-06 Fake never dispatched | Fake incident dispatch attempt → 409 at API and disabled in UI | test + screenshot |
| B6-07 Data integrity under failure | DB restart, worker crash mid-job, network drop on driver app; no report or GPS point lost (CI-7) | logs + counts |

Priority: all P0.

---

# BATCH 7 — Security hardening and deployment

**Objective:** the whole system starts with Docker Compose on one machine over HTTPS (SDS §4.5, NFR-P18) and meets NFR-C1…C11.
**Agents:** A1 lead; A2 (ai-worker/osrm images), A3 (web build, app config). **Prerequisites:** Batch 6.

| Task | Content | Traceability |
|---|---|---|
| B7-01 Full compose stack | `api`, `ai-worker`, `postgres`, `osrm`, `web` (static builds), `nginx`, optional `ollama`; healthchecks; volumes for DB, audio, models | SDS §4.5; NFR-P18 |
| B7-02 TLS (D-024) | nginx TLS, HTTP→HTTPS redirect, WSS; Android trusts the demo CA | NFR-C3; TC-49 |
| B7-03 Secrets and config | All secrets via env; `.env` excluded (already in `.gitignore`); startup refuses default secrets outside dev; secret scan in CI | NFR-C9 |
| B7-04 Security tests | RBAC matrix rerun (TC-48), injection test (TC-50), rate limit (TC-05), CORS restricted, security headers, dependency audit | NFR-C2, C8, C9 |
| B7-05 Backups and audit protection | Encrypted `pg_dump` script; restore test; audit table grants | NFR-C10 |
| B7-06 Data retention | Script to erase simulated data at project end if the supervisor requests | NFR-C11 |
| B7-07 Installation guide | `docs/user-guides/installation.md` with Docker steps on Ubuntu 22.04 | SRS §5.4 |

Priority: P0 (01–04), P1 (05–07).

---

# BATCH 8 — Performance and AI evaluation

**Objective:** measure against NFR-P1…P17 and SDS Table 8.3; tune thresholds; record results honestly.
**Agents:** A2 lead (AI), A1 (load), A3 (usability/compatibility). **Prerequisites:** Batch 7 (measure on the deployment configuration).

| Task | Content | Target / TC |
|---|---|---|
| B8-01 Text latency | 50 text reports one by one, report→dashboard | ≥ 95 % within 10 s (TC-38) |
| B8-02 Voice latency | 20 × 60-s clips | ≥ 95 % within 20 s (TC-39) |
| B8-03 Recommendation latency | triage → recommendation | ≤ 5 s (TC-40) |
| B8-04 Live map / driver latency | GPS → map; approval → driver | ≤ 5 s (TC-41, TC-42) |
| B8-05 Capacity | 50 simultaneous reports + 100 simulated vehicles | no loss, responsive (TC-43) |
| B8-06 Triage accuracy | labelled set | type ≥ 85 %, severity ≥ 80 % |
| B8-07 Duplicate detection | duplicate groups set | ≥ 80 % found, ≤ 5 % wrong merges; tune D-007 weights |
| B8-08 ETA error | predicted vs simulated travel | within 20 % |
| B8-09 Speech accuracy | WER on Urdu/Sindhi clips | reported (text channel stays as backup) |
| B8-10 Usability and compatibility | click count (TC-51), browsers + Android 9+ (TC-52) | ≤ 3 clicks; all pass |
| B8-11 Final LLM choice | close D-008 with evaluation numbers | decision recorded |
| B8-12 Availability during test/demo hours | uptime monitor on `/health` across all test and rehearsal sessions; container restart policies | ≥ 99 % (NFR-P11) |

Results go to `docs/test-reports/`; failures are reported as failures with analysis, not hidden. Priority: P0 (01–05), P1 (06–12).

---

# BATCH 9 — Documentation, demonstration and final acceptance

**Objective:** deliver the documentation listed in SRS §5.4 and pass the supervisor acceptance demo.
**Agents:** all. **Prerequisites:** Batch 8.

| Task | Content | Owner |
|---|---|---|
| B9-01 Dispatcher guide with screenshots | `docs/user-guides/dispatcher.md` | A3 |
| B9-02 Driver one-page quick start | `docs/user-guides/driver.md` | A3 |
| B9-03 Citizen help page | in-app/web help (EN/UR) | A3 |
| B9-04 Admin guide | `docs/user-guides/admin.md` | A3 + A1 |
| B9-05 API description | `docs/API_CONTRACT.md` final + OpenAPI export | A1 |
| B9-06 Test report | all TC-01…TC-52 with status and evidence; AI evaluation | all |
| B9-07 Demo script and video | scenario run: multi-channel intake → AI → review → approve → driver → live map → reports, plus failure/manual mode | all |
| B9-08 SDS v1.1 update note | record approved deviations (D-004 schema, D-002 framework, etc.) for supervisors | all |
| B9-09 Acceptance session | supervisors run prepared simulated incidents (SDS §8.1 acceptance test) | all |

Priority: P0 (06, 07, 09), P1 (others).

---

## 5. Risks

| # | Risk | Effect | Mitigation |
|---|---|---|---|
| R1 | LLM latency or availability (hosted rate limits, local model too slow on CPU) | Misses NFR-P1; demo failure | Gateway with two providers + FakeLLM demo mode; 8-s timeout → manual mode; measure early (B1-A2-17) |
| R2 | Urdu/Sindhi/Roman-Urdu understanding and STT quality | Misses NFR-P7/P8; wrong severity | Few-shot prompts, gazetteer aliases, transcript-unclear warnings, text channel backup, honest reporting |
| R3 | Schema additions (D-004) not approved or changed late | Rework of models/APIs | Approve D-004 before Phase 1B; contracts versioned |
| R4 | Mobile framework (D-002) undecided | Blocks driver workflow (critical path) | Decide first week; PWA fallback limited to citizen mode |
| R5 | Background GPS / FCM restrictions on Android | Missed positions, late alerts | Foreground service, WS primary, SMS backup, test on real devices early |
| R6 | OSRM data preparation (memory, pilot-area extract) | No routes | Small pilot extract; straight-line fallback already designed |
| R7 | Concurrency bugs in locking | Double dispatch (safety) | DB partial unique index + row locks + 50-iteration concurrency test |
| R8 | Duplicate false merges | Hidden emergency (safety) | Conservative thresholds, no status change on link, reversible links, B8 tuning |
| R9 | Self-signed TLS on Android | App cannot connect in demo | D-024 plan; test in B7-02 before demo |
| R10 | Three agents editing shared files | Merge conflicts | Ownership table, CR process, small PRs |
| R11 | Scope vs 9-month timeline | Unfinished "should" items | P0/P1/P2 priorities; PDF export, FCM, channel simulator page are P1/P2 |
| R12 | Dependencies blocked in some environments (seen in this audit: package installs disabled) | Tests not runnable | Run tests in Docker/CI; mark "not verified" honestly |

## 6. Testing strategy (summary)

| Level | Tool | Where | When |
|---|---|---|---|
| Unit | pytest | `backend/tests/unit/` (services, agents) | every task |
| API / integration | pytest + httpx + PostGIS test DB; Postman collection for manual checks | `backend/tests/api/`, `backend/tests/integration/` | every backend task; CI |
| AI evaluation | `tests/ai_eval/run_eval.py` | labelled simulated datasets | B1-A2-17, B8 |
| Web | Jest + React Testing Library (D-015) | `frontend/*/src/**/*.test.tsx` | every UI task; CI |
| Mobile | unit tests + Android checklist | `mobile/`, `docs/test-reports/mobile_checklist.md` | driver tasks, B3 |
| System | SDS TC-01…TC-52 | scenarios + UI | B2–B8 |
| Acceptance | supervisor demo | prepared scenarios | B9 |

Every result is recorded with command, date, environment and pass/fail/blocked/skipped/not-executed.

## 7. Expected final outputs
- Running Docker Compose prototype (api, ai-worker, postgres+PostGIS, osrm, web, nginx) over HTTPS.
- Public report page, dispatcher dashboard, admin panel, Android app (citizen + driver).
- Three AI agents + trust scoring with evaluation report against SRS targets.
- Simulators (SMS, voice, 100 vehicles) and scenario library.
- Test reports for TC-01…TC-52 and AI evaluation; user documentation per SRS §5.4; demo video.

## 8. Recommended first implementation tasks (after approval)
1. Approve D-004, D-005, D-006 (blocking contracts), D-002 (blocking mobile path), D-010, D-011.
2. ~~**B1-A1-02** (make the test harness actually run)~~ — **complete** (see `STATUS.md`). Application code other than the harness is still unverified.
3. Then Phase 1A: B1-A1-03 → B1-A2-01 → B1-A1-04 → B1-A1-05.

