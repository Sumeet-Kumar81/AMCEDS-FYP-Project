# DECISIONS_LOG.md

Records technical, architectural and coordination decisions. Every entry gives the problem, the
options, a **recommendation**, the impact and the **approval status**. "Recommended" never means
approved. Only the team/supervisor can move an entry to *Approved*.

Status values: `OPEN – needs approval` · `APPROVED` · `REJECTED` · `SUPERSEDED`.

---

## 1. Approved decisions

| ID | Decision | Source | Status |
|---|---|---|---|
| A-001 | Modular monolith (FastAPI) + separate AI worker process | SDS §4, project instructions | APPROVED (by SDS) |
| A-002 | Stack: Python 3.11, FastAPI, SQLAlchemy async + asyncpg + GeoAlchemy2 + Alembic, PostgreSQL 15 + PostGIS, LangGraph, LLM Gateway, Whisper/faster-whisper, OSRM + OSM, React, WebSocket, Docker Compose | SDS §4.2, SRS §3.2 | APPROVED (by SDS) |
| A-003 | Human-in-the-loop: AI only recommends; dispatcher approves every dispatch | SRS NFR-S1, SDS §4.4 | APPROVED (by SRS) |
| A-004 | One standard Incident Record shared by every channel and agent | SRS §3.3 Table 3.4, SDS §4.4 | APPROVED (by SDS) |
| A-005 | Three AI agents only: Triage, Coordination, Resource Allocation. Trust scoring is part of Triage (SDS Table 6.3), not a fourth agent | SRS §4.1, SDS Table 6.3 | APPROVED (by SDS) |
| A-006 | Batch 1 is split into exactly three development agents (Backend & DB, AI, Frontend/Mobile/UX) | User planning instruction 2026-11-19 | APPROVED (by instruction) |
| A-007 | Team roles (team slide "Team Roles & Responsibilities", slide 4, provided by the team 2026-11-19): **Arjun Kumar** = AI & Backend development (backend architecture and API, AI agents and emergency triage, resource allocation and intelligent routing); **Khalid Hussain** = Frontend & UI/UX development (UI/UX and dashboard design, frontend and incident visualisation, emergency alerts and dispatcher interfaces); **Sumeet Kumar** = Database & technical support (database design and implementation, dataset preparation and preprocessing, testing, documentation and deployment support). Supersedes the ownership table in `README.md` (which lists Sumeet = frontend, Khalid = DB). | Team slide 2026-11-19 | APPROVED (by team) — the task-level split is D-027b |
| A-008 | Authoritative documents are the Nov 5 SRS (rev 82) and Nov 14 SDS (rev 72) (files `23F-88_SRS.docx`, `23F-88_SDS.docx`), now revised to **SRS v1.1 and SDS v1.1** (2026-11-20). The Oct drafts in the repository (`docs/Requriments/`) are superseded. | D-030, team 2026-11-20 | APPROVED (by team) |
| A-009 | Decisions D-002, D-004, D-005, D-006, D-010, D-011, D-012 and D-020 approved as recommended and written into SRS/SDS v1.1 (details in each entry below) | Team 2026-11-20 | APPROVED (by team) |

---

## 2. Open decisions (need approval before the tasks that depend on them)

Entries marked **APPROVED** below were approved on 2026-11-20 and are kept here for their reasoning.

### D-030 — Which SRS/SDS revision is authoritative
- **Problem:** The repository (HEAD and PR #3) holds the Oct 27 SDS / Oct 29 SRS drafts, while the planning documents were written against the Nov 14 SDS / Nov 5 SRS. Scaffold code comments follow the Oct draft (`incident_record`, `ai_result`).
- **Decision:** The Nov revisions, revised to v1.1 on 2026-11-20, are authoritative. PR #3 must carry these files, not the Oct drafts. Code comments citing the Oct draft are fixed as each file is implemented (see D-003).
- **Status:** APPROVED 2026-11-20 (A-008).

### D-001 — Duplicate `fyp-dispatch/` directory
- **Problem:** `fyp-dispatch/` is a byte-identical copy of the whole repository (checked with `diff -rq`, no differences). Two copies will drift and confuse agents.
- **Options:** (a) delete `fyp-dispatch/` and keep the root as canonical; (b) keep both; (c) move everything into `fyp-dispatch/`.
- **Recommendation:** (a). The root is what README, CI and docker-compose use.
- **Impact:** deletion only; no code change. Blocks B1-A1-01.
- **Status:** APPROVED and DONE 2026-11-21 — option (a). The project developer deleted `fyp-dispatch/` (62 tracked files). Checked before recording: the copy held no unique work (four files were older versions of root files; the only copy-only files were an outdated `docs/README.md` one-liner and five empty `.gitkeep` placeholders). Recoverable from git history.

### D-001b — SRS/SDS not in the repository
- **Problem:** README says "Source of truth: `docs/srs-sds/`" but that folder held only `.gitkeep`; the documents existed only in the Claude Project (and, earlier, as the superseded October drafts in `docs/Requriments/`).
- **Recommendation:** commit the **v1.1** SRS and SDS (A-008) to `docs/srs-sds/`.
- **Current state (2026-11-20):** `SRS_v1.1_clean.docx` and `SDS_v1.1_clean.docx` are committed in `docs/srs-sds/` on `main` (merged via PR #5; commit `2a9356c` renamed them from `docs/SRS-SDS/`, content unchanged). The October drafts and `docs/Requriments/` are no longer on `main`. The tracked-changes copies are not in the repository.
- **Status:** Documentation/state resolved on `main` (the files and the `docs/srs-sds/` path are merged). **Formal team approval of this path decision, if required, is still pending** — this entry does not record any team approval.

### D-002 — Mobile application framework (citizen + driver)
- **Problem:** SRS SW-9 leaves it open ("React Native or Flutter; final choice in design"). SDS Table 4.1 still says "React Native or Flutter (Android)". Project instructions say React Native. The repo README/frontend README plan a **PWA** (`frontend/pwa`) for citizen and driver.
- **Options:** (a) React Native for Android (bare or Expo dev-build); (b) PWA; (c) Flutter.
- **Trade-offs:** UC-08/09 need reliable GPS every 5 s on duty, sound alerts, FCM push, offline queue (CI-7) and geofencing. Background GPS and FCM are reliable in React Native and weak in a PWA on Android. A PWA is faster to build and shares React code.
- **Recommendation:** (a) React Native, in a new top-level `mobile/` folder; keep `frontend/pwa` only for the **public web report page** (renamed `frontend/public-report` if approved). Sub-decision: Expo with development build (simpler tooling, supports background location and FCM) vs bare React Native.
- **Impact:** decides the B1-A3-12…17 file paths; adds a Node/Android toolchain.
- **Status:** APPROVED 2026-11-20 — option (a). Written into SRS v1.1 SW-9 and SDS v1.1 Table 4.1 / Table 4.2. Still open: Expo vs bare React Native; renaming `frontend/pwa`.

### D-003 — Code comments reference a design that is not SDS v1.0
- **Problem:** Scaffold comments cite "SDS Table 3.4", "SDS Table 3.2", "SDS Table 3.10 (WS events)", "SDS 3.2 LLM Gateway", tables `incident_record`, `ai_result`, `system_setting`, column `pipeline_state`. SDS v1.0 has no such tables/sections: its tables are `callers, incidents, incident_groups, users, vehicles, vehicle_locations, recommendations, assignments, hospitals, audit_logs, settings` (SDS §5.2), and business rules are in SRS Appendix C (Tables 7.3.1–7.3.4).
- **Question to team:** is there a newer SDS revision? If not, SDS v1.0 governs.
- **Recommendation:** treat SDS v1.0 as authoritative; fix the comments as each file is implemented (no separate cleanup task).
- **Status:** Answered by D-030: the comments follow the superseded Oct draft. SDS v1.1 governs; comments are fixed as each file is implemented.

### D-004 — Schema additions needed beyond SDS §5.2
- **Problem:** SDS §5.2 cannot satisfy several SRS requirements on its own:

| Requirement | Gap in SDS tables | Proposed addition |
|---|---|---|
| UC-01 reference number "INC-000123" (SRS §7.2) | none (derivable) | `incidents.reference_no` text unique, `INC-` + 6-digit id, set in the same transaction |
| UC-01 5a / TC-04 offline resend creates one record | no idempotency | `incidents.client_request_id` text unique nullable |
| UC-01 step 4 optional name | `callers` has no name | `incidents.reporter_name` text |
| UC-03 GPS vs message location | only one `location` | `incidents.caller_gps` geometry(Point,4326) separate from resolved `location` |
| Worker hand-off, retries, manual fallback | no pipeline fields | `incidents.pipeline_state` (pending, processing, done, failed, reallocate), `pipeline_attempts`, `pipeline_error`, `pipeline_updated_at` |
| UC-02 per-field confidence, unclear transcript, missing info; NFR-S9 log AI result | only one `confidence` | `incidents.ai_details` JSONB (per-field confidence, flags, model, prompt version, latency) + `review_reasons` text[] |
| UC-03 reasons for trust decisions | only score/tier | `incidents.trust_signals` JSONB (signal list with points) |
| UC-12 "new settings apply only to new incidents" | none | `incidents.settings_snapshot` JSONB written at intake |
| UC-04 possible duplicates awaiting dispatcher | only `group_id` | new table `duplicate_candidates` (incident_id, candidate_incident_id, match_confidence, distance_m, time_diff_s, similarity, decision, decided_by, decided_at) |
| UC-03 6 / UC-07 2 caller confirmation | none | new table `confirmation_requests` (incident_id, channel, token_hash, sent_at, response, responded_at) |
| UC-05 approximate ETA, vehicle type, spare flag, route preview, re-runs | none | `recommendations.vehicle_type`, `eta_is_approximate`, `is_spare`, `route_geometry` (encoded polyline text), `batch_no`, `is_current`; `incidents.allocation_summary` JSONB (needed per type, shortage warning, victims-unknown flag) |
| UC-08 2a decline reason, 2b timeout | only status | `assignments.decline_reason`, `declined_at`, `timed_out_at`, `notified_at` |
| NFR-S6 one open assignment per vehicle | none | partial unique index on `assignments(vehicle_id) WHERE status IN ('approved','accepted')` |
| UC-11 lockout, idle timeout, logout, duty | none | `users.failed_login_count`, `locked_until`, `on_duty`; new table `user_sessions` (jti, user_id, last_activity_at, revoked_at) — see D-023 |
| NFR-C10 audit not editable | none | DB trigger/grant blocking UPDATE/DELETE on `audit_logs` |
| NFR-S9 / UC-06 log "what AI suggested vs what was chosen" queryably | `audit_logs.details` is text | `audit_logs.details` as JSONB |
| UC-01 5b / Table 7.3.1 device flood signal | none | `callers.flagged_until` timestamptz |
| NFR-S5 worker health on dashboard | none | `worker_heartbeats` (worker_id, last_seen_at, info JSONB) — tiny table |
| UC-08 alert payload ETA / O8 manual baseline | none | stored in `allocation_summary` / `ai_details.handled_mode` (no new column) |

- **Options:** (a) add the columns/tables above (recommended); (b) put everything into JSON fields of SDS tables; (c) add separate tables for every concept (ai_results, trust_assessments, review_items…).
- **Recommendation:** (a). It keeps SDS tables and names, adds two small tables, and keeps the review queue as a *query* (`status = 'needs_check'` or open review reasons) rather than a separate table.
- **Impact:** B1-A1-04…08 models and first migration. The SDS should get a v1.1 note.
- **Status:** APPROVED 2026-11-20 — option (a), the full list. Written into SDS v1.1 §5 (extra columns in Tables 5.1, 5.2, 5.4, 5.7, 5.8, 5.10; new Tables 5.12 `duplicate_candidates`, 5.13 `confirmation_requests`, 5.14 `user_sessions`, 5.15 `worker_heartbeats`; partial unique index note under Table 5.8). Implementation is still staged: the Milestone 1 columns first, the rest in their own Alembic migration with the task that needs them. SDS Figures 2.2 and 5.1 still need redrawing to show the additions.

### D-005 — Status vocabularies
- **Problem:** SRS/SDS use phrases ("needs check", "needs more information", "on scene"). Code needs fixed enum values.
- **Recommendation:**
  - `incidents.status`: `new, triaged, needs_check, dispatched, on_scene, closed, fake`. "Needs more information" is `needs_check` with review reason `missing_info` (SDS §5.2 lists only these seven).
  - `vehicles.status`: `available, assigned, en_route, on_scene, transporting, at_hospital, offline` (`at_hospital` added for UC-09 step 3; SDS lists six).
  - `assignments.status`: `approved, accepted, declined, timed_out, completed` (SDS) + `cancelled` (vehicle freed by dispatcher).
  - `channel`: `voice, sms, web, app` (SDS §5.2; the existing schema uses `mobile` — rename to `app`).
  - `incident_type`: `accident, fire, medical, other`; `severity`: `low, medium, high, critical`; `vehicle_type`: `ambulance, fire_truck, backup`; `trust_tier`: `high, medium, low`; `location_source`: `gps, text, unknown`.
- **Status:** APPROVED 2026-11-20 — values as listed, stored as text with CHECK constraints (not native PostgreSQL enums). Written into SDS v1.1 §5 and Tables 5.2, 5.5, 5.8, and SRS v1.1 Table 3.4 / §7.2 / UC-02 2a. `pipeline_state` values: `pending, processing, done, failed, reallocate`.

### D-006 — API endpoint design (SDS has none)
- **Problem:** Project instructions say "follow the SDS endpoint design", but SDS v1.0 contains no endpoint list.
- **Recommendation:** Agent 1 publishes `docs/API_CONTRACT.md` (endpoint list in IMPLEMENTATION_PLAN §4.3) in Phase 1A, the team approves it, and FastAPI's `/openapi.json` becomes the machine-readable contract. Prefix all routes with `/api/v1` (the existing `/reports` and `/health` move under it; the two existing tests are updated in the same task).
- **Status:** APPROVED 2026-11-20 — endpoint list and WebSocket events written into SDS v1.1 §4.6 (Tables 4.3 and 4.4), all under `/api/v1` except an unprefixed `GET /health` for the Docker healthcheck; unbuilt endpoints return 501, never fake data. `docs/API_CONTRACT.md` (request/response bodies) is still to be written in B1-A1-04.

### D-007 — Duplicate match-confidence formula and text similarity
- **Problem:** SRS gives thresholds (≥ 85 / 60–84 / < 60) and gates (same type, 300 m, 15 min) but no formula. The scaffold comment proposes `100 × (0.40·S_dist + 0.20·S_time + 0.40·S_meaning)` and sentence-transformers. SDS says "Rules + text similarity".
- **Options for S_meaning:** (a) multilingual sentence-transformer (new dependency, model download, better on Urdu/Roman-Urdu); (b) TF-IDF/character n-gram cosine (light, weaker); (c) LLM similarity call (slow, costs a model call per pair).
- **Recommendation:** weights as proposed, all configurable in `settings`; S_dist = 1 − d/300 m, S_time = 1 − Δt/15 min; S_meaning by (a) if the dependency is approved, otherwise (b). Tune with `db/eval_data/duplicate_groups.jsonl` against NFR-P9 (≥ 80 % found, ≤ 5 % wrong merges).
- **Amendment (2026-11-20, see D-033):** the linear S_dist/S_time above cannot reach 85 at TC-13 (a perfect text match 100 m and 5 min away scores 80). Quadratic decay is proposed in D-033.
- **Status:** OPEN – needs approval (dependency).

### D-008 — Language model provider
- **Problem:** SRS SW-3: "open-weight such as Llama or Mistral, or a hosted model; chosen after tests". `.env.example` defaults to Groq (hosted).
- **Recommendation:** the Gateway supports one local provider (Ollama) and one hosted provider (Groq) plus a deterministic `FakeLLMClient` for tests. Pick the default after the B1-A2-17 evaluation. Hosted use is acceptable only because all data is simulated (NFR-C7).
- **Status:** PROVISIONALLY APPROVED 2026-11-21 by the project developer — Groq (hosted Llama, `LLM_MODEL=llama-3.3-70b-versatile`) through its OpenAI-compatible HTTP API with `httpx` (no SDK added), Ollama as the local alternative, `FakeLLMClient` in all tests. The final default is still chosen after the B1-A2-17 evaluation. Implemented in `backend/app/llm/` (B1-A2-02).

### D-009 — Geocoding source
- **Problem:** SDS says Nominatim. The repo plans a local pilot gazetteer "instead of local Nominatim". Public Nominatim allows at most about 1 request/s and needs internet.
- **Recommendation:** gazetteer first (landmarks with EN/Urdu/Roman-Urdu aliases), public or self-hosted Nominatim as fallback, `location_source = unknown` with a dispatcher warning if both fail. The gazetteer adds to Nominatim and does not replace it.
- **Status:** OPEN – needs approval.

### D-010 — How the worker receives jobs and returns events
- **Problem:** The worker is a separate process; the WebSocket hub lives in the API process.
- **Options:** (a) DB polling with `SELECT … FOR UPDATE SKIP LOCKED` on `incidents.pipeline_state`; events via Postgres `LISTEN/NOTIFY` consumed by the API; (b) Redis queue/pub-sub (new service, not in SDS); (c) worker calls an internal API endpoint.
- **Recommendation:** (a). No new infrastructure, survives worker crashes (state stays in DB), and NOTIFY payloads stay small (event name + incident id; the API re-reads the row). Add NOTIFY on insert so pick-up is immediate (needed for NFR-P1 10 s).
- **Status:** APPROVED 2026-11-20 — option (a). Written into SDS v1.1 §3.1, §4.3, §4.6 and Table 4.2. Build order: polling first (about 1 s), LISTEN/NOTIFY added for speed and events.

### D-011 — Where intake/speech-to-text runs (SDS §4.5 vs §3.1)
- **Problem:** SDS §4.5 puts the "Intake and Fusion service" inside the `ai-engine` container, while §3.1 and NFR-P12 require the Incident Record to be saved before any AI step and the caller to get a reference number immediately.
- **Recommendation:** API `IntakeService` saves the raw record (text or audio file reference, GPS or address text, channel, caller) and returns the reference at once. The worker then does speech-to-text and geocoding as the first graph nodes. The SDS layering is kept and the safety rule is met.
- **Status:** APPROVED 2026-11-20 — as recommended. Written into SRS v1.1 UC-01 step 5 and SDS v1.1 §3.1, §4.1, §4.3, §4.5 (container renamed `ai-worker`), Tables 4.1, 4.2 and 6.3. SDS Figures 3.1, 4.1 and 6.3 still show the old placement and need redrawing.

### D-012 — Trust scoring placement and inputs
- **Problem:** SDS Table 6.3 gives trust to TriageAgent. The scaffold has a separate `agents/trust.py` "plain Python, not LLM".
- **Recommendation:** `TrustScorer` is a deterministic module inside the Triage step (not an agent and not an LLM decision). The "real details" and "vague/joking" signals come from triage output flags. "Independent nearby reports" means distinct callers/devices of the same type within the duplicate distance and window. Low LLM confidence alone never lowers trust or marks a report fake.
- **Status:** APPROVED 2026-11-20 — as recommended. Written into SRS v1.1 UC-03 actors and Glossary, and SDS v1.1 §1.2, §3.1, §3.3, §4.3, Tables 4.1, 4.2 and 6.3 (new `TrustScorer` class row). SDS Figure 6.3 still needs the class added.

### D-013 — Driver notifications (FCM)
- **Problem:** SRS depends on FCM, which needs a Firebase project and `google-services.json`. NFR-P5 requires 5 s.
- **Recommendation:** `NotificationService` with adapters: WebSocket to the logged-in driver app (primary for the demo), FCM push (if a free Firebase project is set up), SMS to the driver via the simulator when the app is unreachable (UC-06 4b).
- **Status:** OPEN – needs approval and a Firebase project owner.

### D-014 — SMS and voice channel simulation
- **Problem:** Real 1122 line and SMS gateway are out of scope (SRS §1.5).
- **Recommendation:** `POST /api/v1/intake/sms` and `POST /api/v1/intake/voice` simulator webhooks protected by a shared secret, driven by `db/simulators/sms_simulator.py` and a small "Channel Simulator" developer page in the dashboard, labelled SIMULATED everywhere.
- **Status:** OPEN – needs approval. (The two endpoints are listed in SDS v1.1 Table 4.3.)

### D-015 — Web frontend structure and test runner
- **Problem:** Repo plans two Vite apps with React + TypeScript + Tailwind + Leaflet. SDS specifies React and Leaflet/MapLibre; TypeScript and Tailwind are not mentioned. SDS §8.1 names Jest; Vite projects usually use Vitest.
- **Recommendation:** React + TypeScript + Leaflet (allowed by SDS); Tailwind acceptable (styling only). Use Jest + React Testing Library as the SDS says, or approve Vitest (Jest-compatible API) as a recorded deviation.
- **Decision (2026-11-22, approved by the project developer (sole developer), with the F1 frontend plan):** React 19 + TypeScript + Vite in an npm workspace `frontend/` (`shared`, `dashboard`, `pwa`, one lock file); **Vitest + React Testing Library + jsdom** instead of Jest — a recorded deviation from SDS §8.1 (same test style and API; works with Vite without extra setup); **plain CSS** with shared colour tokens, no Tailwind (fewer dependencies); English/Urdu text with a small in-house hook, no i18n library; API types generated from `/openapi.json` with `openapi-typescript`. Every package pinned to an exact version published at least two weeks earlier; `npm audit` 0 vulnerabilities. TypeScript stays on 5.9.3 because `openapi-typescript` 7.13 requires TypeScript 5. `react-router-dom` and `@tanstack/react-query` are approved but added only in the group whose screens use them (F3/F4). Leaflet comes with the map task.
- **Status:** APPROVED 2026-11-22 (project developer).

### D-016 — Driver turn-by-turn navigation
- **Problem:** UC-08 requires navigation that opens automatically, recalculates off-route and needs no typing.
- **Options:** (a) in-app map with an OSRM route, step list and Android text-to-speech prompts, recomputed when off-route; (b) launch the Google Maps navigation intent with destination coordinates; (c) both, with (b) as fallback.
- **Recommendation:** (c). (a) keeps the OSRM design and works with cached tiles (UC-08 3a); (b) is a fallback the driver opens with one tap.
- **Status:** OPEN – needs approval.

### D-017 — Performance and accuracy targets
- SRS §2.6 says the NFR-P targets need supervisor confirmation. **Status:** OPEN – supervisor.

### D-018 — Hospital suggestion rule
- **Problem:** UC-09 step 2 "checks the suggested hospital" but no rule is given.
- **Recommendation:** nearest active hospital by OSRM ETA from the incident whose `departments` match the incident type (fallback: nearest active). Dispatcher can change it (UC-09 2a).
- **Status:** OPEN – needs approval.

### D-019 — Vehicle rules not fully specified
- **Problem:** Meaning of "backup vehicle"; accident without injuries; "Other: 1 vehicle chosen by the dispatcher".
- **Recommendation:** `backup` is the SDS vehicle type `backup`; accident with 0 victims → 1 ambulance with "dispatcher check" flag; `other` → no automatic type, show all available vehicles nearest-first and require dispatcher choice.
- **Extensions (2026-11-20, from the blueprint, U-3/U-4):** (1) unknown victim count = 1 vehicle **per required type** plus a dispatcher-check flag (a fire needs a truck and an ambulance even when the count is unknown); (2) "+ 2 spare" means 2 spare vehicles in total, the best remaining vehicles of the needed types, not 2 per type.
- **Status:** APPROVED 2026-11-21 by the project developer — recommendation and both extensions: accident with 0 victims → 1 ambulance + "please check"; `other` (or type unknown) → every available vehicle nearest-first, dispatcher chooses; victims unknown → 1 vehicle of each needed type + "please check"; "+ 2 spare" = 2 in total. Implemented in `agents/resource.py` (B1-A2-11).

### D-020 — UC-04 alternate 5a wording conflict
- **Problem:** UC-04 5a text is garbled (mentions sending an extra vehicle). TC-15 and NFR-S4 say an unanswered medium-confidence match keeps reports **apart**.
- **Recommendation:** follow TC-15/NFR-S4: keep separate; each report is dispatchable on its own.
- **Status:** APPROVED 2026-11-20 — SRS v1.1 UC-04 5a now says the reports stay separate and each can be dispatched on its own.

### D-021 — Allocation for low-trust, low/medium-severity reports
- **Problem:** UC-07 step 3 says "Real → goes on to UC-05", implying no recommendation before review. Running allocation anyway costs nothing and never locks vehicles.
- **Recommendation:** follow the SRS literally: skip allocation for low tier + low/medium severity until marked Real (then run it in ≤ 5 s, NFR-P3). High/critical are always allocated immediately.
- **Status:** APPROVED 2026-11-21 by the project developer — no recommendation for a low-tier, low/medium-severity report until it is marked Real; high/critical (and unknown severity) always get vehicles at once. Implemented as `agents/policy.py` `allocate_now`.

### D-022 — Report flood thresholds
- **Problem:** UC-01 5b / NFR-C8 / TC-05 ("10 reports in one minute → pause a few minutes") give no exact numbers.
- **Recommendation:** default max 5 reports per device or phone per 10 minutes, then block for 10 minutes (HTTP 429 with a message pointing to the 1122 call notice). Admin-configurable. The blocked attempt is still logged; the flood flag feeds the −20 trust signal.
- **Status:** APPROVED 2026-11-21 by the project developer — as recommended: at most 5 reports per device or phone in 10 minutes, then blocked for 10 minutes. Stored as settings `rate_limit_reports`, `rate_limit_window_min`, `rate_limit_block_min` (admin-configurable, B1-A1-12); enforced in B1-A1-18.

### D-023 — Session design (idle timeout, logout, driver exemption)
- **Problem:** NFR-C4 30 min idle logout; UC-11 1b drivers with an active assignment stay signed in; logout must end the session. Stateless JWT alone cannot do idle timeout or revocation.
- **Recommendation:** short-lived JWT access token (15 min) carrying a session id `jti`; `user_sessions` row updated on each request (`last_activity_at`); refresh endpoint rejects sessions idle > 30 min unless the user is a driver with an open assignment; logout sets `revoked_at`.
- **Status:** APPROVED 2026-11-21 by the project developer — as recommended (15-minute access token with `jti`; refresh refused after 30 min idle unless a driver has an open assignment; logout sets `revoked_at`). Written into contract C-3 (`backend/app/schemas/auth.py`). Note: `core/config.py` still has `jwt_expire_minutes = 30`; B1-A1-14 sets it to 15. (The `user_sessions` table itself is in SDS v1.1 Table 5.14 under D-004.)

### D-024 — HTTPS in the local prototype
- **Problem:** NFR-C3/TC-49 require TLS. Android apps reject self-signed certificates by default.
- **Recommendation:** nginx container with a locally generated CA (e.g. mkcert); install the CA on the demo phone, or allow it via Android network-security-config in debug builds only. Plain HTTP port 80 redirects to HTTPS.
- **Status:** OPEN – needs approval.

### D-025 — Manual baseline for UC-13 response-time comparison
- **Problem:** UC-13 / O8 compare AI-assisted vs manual response time; no manual data source is defined.
- **Recommendation:** a "manual mode" toggle on the dashboard (AI panels hidden). Timed sessions with the same simulated scenarios produce the baseline, and incidents carry `handled_mode` (`ai_assisted|manual`) in `ai_details`.
- **Status:** OPEN – needs approval.

### D-026 — Stations
- **Problem:** Project instructions mention managing stations; SDS has only `vehicles.station_name` text and no stations table.
- **Recommendation:** follow SDS (text field with a fixed pick-list in settings). Add a table only if the team approves.
- **Status:** OPEN – needs approval.

### D-027 — Mapping of development agents to team members
- **Resolved by A-007** (team slide). Original problem: README ownership (backend/app = Arjun, frontend = Sumeet, db/migrations/infra = Khalid) contradicted the roles the team now states.
- **Status:** RESOLVED (roles). The task-level split and README update are tracked in D-027b.

### D-027b — Task-level split of Batch 1 between team members, and README ownership table
- **Problem:** The slide gives roles, not tasks. The three development agents (Agent 1 Backend & DB, Agent 2 AI, Agent 3 Frontend/Mobile) are *workstreams*; the team members own them as below. Agent 1 spans two people because the slide gives "backend architecture and API" to Arjun but "database design and implementation" to Sumeet.
- **Proposed split (needs team confirmation):**

| Person | Workstream | Batch 1 tasks |
|---|---|---|
| **Arjun Kumar** | Agent 1 — API and services | B1-A1-03, 04, 05 (contracts C-1, C-3–C-7), 14, 15, 16, 17, 18, 20–30, 33 |
| **Arjun Kumar** | Agent 2 — AI, triage, resource allocation, routing (all) | B1-A2-01 … B1-A2-15, B1-A2-17 (code); also owns contract C-2 |
| **Khalid Hussain** | Agent 3 — Frontend, UI/UX, alerts, dispatcher interfaces | B1-A3-01 … B1-A3-19 (**including the Android app** — assumption, see below) |
| **Sumeet Kumar** | Agent 1 — database and technical support | B1-A1-01 (repo hygiene), 02 (test harness), 06–11 (Alembic, all models, initial migration), 12 (settings service), 13 (audit service), 19 (pipeline persistence SQL), 31 (admin APIs), 32 (analytics SQL and export), 34 (seed data) |
| **Sumeet Kumar** | Data, testing, docs, deployment support | B1-A2-16 (evaluation datasets), B1-A2-05 gazetteer *data*, B1-A2-10 OSRM data preparation and container, B1-A3-19 CI wiring, simulators in `db/simulators/` (B4-03, B4-05 data), Batch 6 test reports, Batch 7 deployment, Batch 8 measurement runs, Batch 9 documentation and user guides |

- **Assumptions to confirm:** (1) The slide says "Frontend & UI/UX" for Khalid; the Android citizen/driver app is **not mentioned** for anyone. The plan assigns it to Khalid with the web UI. (2) The routing *code* (`integrations/routing.py`) is Arjun's ("intelligent routing"); the OSRM map data and container are Sumeet's ("deployment support"). (3) Sumeet writes user guides; Khalid supplies screenshots and UI text.
- **Workload risk:** Arjun would carry about 36 of 70 Batch 1 tasks (all AI plus the API). Khalid carries 19 (including mobile), Sumeet about 14 plus data, testing, docs and deployment. Options: (a) accept; (b) move more DB-adjacent API work (for example B1-A1-20, 22, 23) to Sumeet; (c) move simple driver-facing endpoints to Khalid after contracts are frozen. Recommendation: (a) for now, review after Phase 1B.
- **README:** `README.md` "Ownership" table still shows the old assignment (Sumeet = frontend, Khalid = DB). It must be changed in a PR after approval; it was not edited in this planning session.
- **Status:** SUPERSEDED 2026-11-21 — the project has one developer, who does every task (see D-034). The roles in A-007 stay as the documented team roles. The README ownership table is still outdated (B1-A1-01).

### D-028 — Public OSM tile usage
- **Problem:** The public OSM tile server has a usage policy and needs internet; UC-08 3a needs a stored map area.
- **Recommendation:** public tiles for the demo with attribution; pre-cache pilot-area tiles in the driver app; optional self-hosted tiles later.
- **Status:** OPEN – needs approval.

### D-029 — Background scheduler for timers
- **Problem:** 60 s assignment timeout, 60 s lost signal and confirmation expiry need a timer.
- **Recommendation:** single asyncio background loop started in the API lifespan (`services/scheduler.py`), every 5 s, using DB timestamps (restart-safe). Assumes one API instance (true for the prototype).
- **Status:** OPEN – needs approval.

### D-031 — Mapping of the master-prompt table list to the approved SDS schema
- **Problem:** The blueprint prompt names tables (roles and permissions, drivers, trust scores, AI processing results, dispatcher decisions, incident status history) that the approved SDS v1.1 stores differently. Building both would duplicate data.
- **Options:** (a) keep the SDS schema and map each name to where the data lives; (b) add the extra tables.
- **Recommendation:** (a). Role is a column on `users`; a driver is a `users` row with `role='driver'` linked one-to-one to `vehicles`; trust and AI results are columns and JSONB on `incidents`; dispatcher decisions are `assignments` plus `audit_logs`; status history is audit rows. Add a table only if a measured need appears. Mapping table: `docs/blueprint/04_DATABASE.md` §4.2.
- **Impact:** no schema change beyond D-004.
- **Status:** APPROVED 2026-11-21 — option (a), by the project developer.

### D-032 — Calendar, pilot area and viva dates
- **Problem:** The SRS and SDS give no start date, submission date, viva date or exact pilot area, so the nine-month plan cannot be tied to dates, and the OSRM extract, gazetteer and simulated vehicle positions need an area.
- **Recommendation:** the team supplies the dates and the pilot area in week 1; until then the roadmap uses weeks 1–36.
- **Status:** PARTLY DECIDED 2026-11-21 by the project developer. **Pilot area: Sukkur district** (OSRM extract, gazetteer and simulated vehicle positions use it). **Dates: not known yet** — the roadmap stays in weeks 1–36 until the start, submission and viva dates are known.

### D-033 — Duplicate formula decay (amends D-007)
- **Problem:** With linear decay the best possible score at TC-13 (100 m, 5 min, identical meaning) is 80, below the 85 auto-link threshold, so TC-13 and NFR-P9 cannot pass. Shown by the test `test_finding_linear_decay_can_never_auto_link_tc13` in `docs/blueprint/code_sketches/`.
- **Options:** (a) quadratic decay `s_dist = max(0, 1 − (d/300)²)`, `s_time = max(0, 1 − (Δt/15)²)`; (b) lower the auto-link threshold (contradicts the SRS); (c) change the weights.
- **Recommendation:** (a), weights 0.4 / 0.2 / 0.4 and the decay exponent kept as settings; gives 93 at TC-13; tune on `duplicate_groups.jsonl` against NFR-P9.
- **Impact:** only the scoring function; thresholds in the SRS unchanged.
- **Status:** APPROVED 2026-11-21 by the project developer — quadratic decay, weights 0.4 / 0.2 / 0.4 stored as settings `dup_weight_distance`, `dup_weight_time`, `dup_weight_meaning` (they must add up to 1). Still open under D-007: how `s_meaning` (text similarity) is computed (new dependency or not).

### D-034 — Task-level rebalance of Batch 1 (extends D-027b)
- **Problem:** D-027b gave Arjun about 36 of 70 Batch-1 tasks (all AI plus most of the API).
- **Recommendation:** Arjun 23 (AI, contracts, orchestration), Khalid 19 (web and Android), Sumeet 28 (database, services, admin, analytics, data, tests, deployment). Dependency-checked by `docs/blueprint/tools/schedule_check.py` (0 violations; all 70 tasks scheduled). The 36-week table is `11_ROADMAP_9_MONTHS.md`. Team may choose differently.
- **Status:** SUPERSEDED 2026-11-21 — not applicable: the project has one developer, who does all 70 Batch-1 tasks in the dependency order of `docs/blueprint/11_ROADMAP_9_MONTHS.md`. The per-person columns of that roadmap are no longer a split of work.

### D-035 — Trust tier when Triage fails
- **Problem:** NFR-S2 wants a trust tier on every report, but if Triage fails the inputs "real details" and "vague or joking" do not exist.
- **Recommendation:** run the Trust Scorer on its non-LLM signals (caller history, GPS distance, nearby independent reports, flood flag), show the tier with an "AI unavailable" note, and never mark the report fake because of the failure.
- **Status:** APPROVED 2026-11-21 by the project developer — as recommended; the tier comes from the non-LLM signals and an `ai_unavailable` (0 points) reason is shown. Implemented in `agents/trust.py`.

---

## 3. Shared contracts (owner, consumers, version)

Agreement order (Phase 1A of Batch 1): C-1 → C-2 → C-3 → C-4 → C-5 → C-6 → C-7.

| ID | Contract | Owner | Consumers | Location (planned) | Version / status |
|---|---|---|---|---|---|
| C-1 | Enums + Incident Record read schema (`IncidentSummaryOut`, `IncidentDetailOut`) | Agent 1 | A2, A3 | `backend/app/schemas/enums.py`, `schemas/incident.py` | v1.1 — v1 approved 2026-11-20; v1.1 (2026-11-21) adds optional `detail` to `TrustSignalOut` to match C-2 (backward compatible). Notes below |
| C-2 | AI result schemas: `TriageResult`, `TrustAssessment`, `DuplicateCandidateResult`, `AllocationResult`, `VehicleRecommendation` | Agent 2 | A1 (stores), A3 (displays) | `backend/app/schemas/ai.py` | v1 — approved by the project developer (sole developer, acting as A1, A2 and A3), 2026-11-21. Notes below |
| C-3 | Auth: login request/response, token claims, `/me` user shape, role names | Agent 1 | A3 | `schemas/auth.py` | v1.1 — v1 approved 2026-11-21; v1.1 (B1-A1-14) adds `RefreshTokenClaims` (refresh token = JWT of type `refresh` with the session's `jti`, absolute lifetime 12 h, developer assumption). Endpoints built |
| C-4 | REST endpoint list and request/response bodies | Agent 1 | A3, A2 (reallocation/routing proxy) | `docs/API_CONTRACT.md` + `/openapi.json` | v1 — approved by the project developer (sole developer), 2026-11-21: `docs/API_CONTRACT.md` + `/openapi.json`; 48 endpoints, 501 until built |
| C-5 | WebSocket event envelope and event names; NOTIFY payloads from worker | Agent 1 (A2 emits via NOTIFY) | A3, A2 | `schemas/events.py`, `docs/API_CONTRACT.md §WS` | v1 — approved by the project developer (sole developer), 2026-11-21; 18 events of SDS Table 4.4; `docs/API_CONTRACT.md` §4. Notes below |
| C-6 | Pipeline persistence interface (claim job, save stage results, mark failed, candidate queries) | Agent 1 | A2 | `backend/app/services/pipeline_store.py` | v1 — interface only, approved by the project developer, 2026-11-21; implementation in B1-A1-19. Notes below |
| C-7 | Driver assignment payload + trip status transitions | Agent 1 | A3 | `schemas/assignment.py` | v1 — approved by the project developer, 2026-11-21. Notes below |


**C-1 notes (v1, 2026-11-20).** Decided by the project developer, who is the only developer on the project (there are no separate A2/A3 reviewers):
1. The SRS Table 3.4 / §7.2 field `vehicles` ("recommended and assigned") is carried by `IncidentDetailOut.recommendations` (current round) and `IncidentDetailOut.assignments`. There is no separate `vehicles` field.
2. `caller_gps`, `caller_id`, `client_request_id`, `settings_snapshot` and the `pipeline_*` columns are not part of the C-1 read schemas. A screen that needs one later adds it through a coordination request (§4).
3. Recommendation rounds start at 1, so `RecommendationOut.batch_no` keeps `ge=1`.
4. The real `POST /reports` (B1-A1-16) returns `reference_no` (string, e.g. `INC-000123`); `incident_id` stays an integer.
Also fixed in v1: `eta_seconds` and `distance_meters` are required (an approximate ETA still has a value); `location` is required and "no location" is `source = "unknown"`; `gps` needs lat/lon, `text` needs the address words (coordinates are added when the worker geocodes, D-011).

**C-2 notes (v1, 2026-11-21).** Decided by the project developer. Where the B1-A2-01 task text differed from C-1 v1, C-1 wins:
1. Duplicate decisions use the C-1 values. The Coordination Agent may only propose `auto_linked`, `possible` or `separate` (the plan text said `auto_link`); `confirmed` and `rejected` are dispatcher decisions. The exported JSON Schema lists only the three agent values.
2. The route field is `route_geometry` (C-1, SDS Table 5.7), not `route_polyline`.
3. A trust signal is `{code, points, detail}`; `detail` (the reason) is required in C-2 and optional in C-1 v1.1.
4. The allocation hospital suggestion is `hospital_id: int | None` only; the rule stays open (D-018).
5. No "AI unavailable" field yet: D-035 is still open.
6. Which C-2 objects are stored in C-1 `ai_details` / `allocation_summary` is decided in B1-A1-19 (storage).
Admin-configurable thresholds (trust tiers, duplicate 85/60, vehicle rules) are enforced by the agents and settings, not by the schemas.

**C-5, C-6, C-7 notes (v1, 2026-11-21).** Decided by the project developer:
1. C-7: a vehicle may go from `on_scene` straight to `available` (no patient carried, e.g. a fire truck). UC-09 describes only the trip through a hospital.
2. C-7: the driver payload carries `respond_by` (alert time + the answer limit, default 60 s from SRS Appendix C) so the app can show a countdown.
3. C-6: `save_trust` takes only the C-2 `TrustAssessment`, which already contains the action (the plan text listed the action separately).
4. C-6: the worker claims only `pending` and `reallocate` jobs. "retrust" (mentioned in B1-A2-15) is not an approved `pipeline_state` (D-005) and is decided in B1-A2-15.
5. C-5: the worker may raise only the six events whose "Sent by" in SDS Table 4.4 includes the AI worker, and only through `NOTIFY incident_events` with `{event, incident_id}` (D-010). A new vocabulary `PipelineStage` (speech_to_text, geocoding, triage, trust, coordination, allocation) names the failed step.
6. C-7: vehicle status on accept is `en_route` (UC-08 step 3, navigation starts); decline, time-out, cancel and completion free the vehicle (`available`).
---

## 4. Coordination requests (CR)

Template: `CR-xxx | date | from agent | to owner | file/contract | change wanted | reason | status`.

| CR | Date | From | To | File | Change | Reason | Status |
|---|---|---|---|---|---|---|---|
| CR-001 | 2026-11-21 | A1 (B1-A1-34) | project developer | `.env.example` | add empty `SEED_ADMIN_PASSWORD`, `SEED_DISPATCHER_PASSWORD`, `SEED_DRIVER_PASSWORD`; reword the business-rules comment | seed accounts get passwords only from the environment, never from code | APPROVED and done 2026-11-21 |
| CR-002 | 2026-11-21 | A1 (B1-A1-14) | project developer | `.env.example` | add `ENV=dev`; `JWT_EXPIRE_MINUTES` 30 → 15 (D-023) | startup refuses weak JWT secrets outside dev; access tokens last 15 min | APPROVED and done 2026-11-21 |
| CR-003 | 2026-11-21 | A2 (B1-A2-13) | project developer | `backend/requirements.txt` | add `langgraph==1.2.24` (pinned; installs cleanly on python:3.11-slim, `pip check` clean) | the SDS (§4.2) names LangGraph for the agent orchestrator; Groq is called over `httpx`, so no LLM SDK is added (D-008) | APPROVED and done 2026-11-21 |

---

## 5. Decision history

| Date | Entry | Change |
|---|---|---|
| 2026-11-19 | A-001…A-006, D-001…D-029, C-1…C-7 | Created during planning (documentation only; nothing approved by this session) |
| 2026-11-19 | A-007, D-027 (resolved), D-027b (new) | Team roles from the team slide recorded; task-level split proposed |
| 2026-11-20 | A-008, A-009, D-030 (new, approved); D-002, D-004, D-005, D-006, D-010, D-011, D-012, D-020 approved; D-003 answered | Team chose the Nov SRS/SDS and approved the recommendations; all written into SRS/SDS v1.1 |
| 2026-11-20 | D-031…D-035 (new, open); D-019 extended; D-007 amended note | Added by the implementation blueprint (`docs/blueprint/`); nothing approved by this session |
| 2026-11-21 | D-008 (provisional), CR-003 | Groq over httpx + Ollama + fake model for tests (B1-A2-02); `langgraph==1.2.24` added for the orchestrator (B1-A2-13) |
| 2026-11-22 | D-015 approved | Frontend stack for F1 (B1-A3-01, 02): React + TypeScript + Vite workspace, Vitest + React Testing Library (deviation from SDS Jest), plain CSS, generated API types; approved by the project developer (sole developer) |
