# PROJECT_CONTEXT.md

> Read this first. It explains the project without relying on any earlier conversation.
> Primary sources of truth: **SRS v1.0** and **SDS v1.0** (`SRS_AI_Emergency_Dispatch_System.docx`,
> `SDS_AI_Emergency_Dispatch_System.docx`). They are currently held in the team's Claude Project and
> are **not yet committed** to `docs/srs-sds/` (see DECISIONS_LOG D-001b). When this file and the
> SRS/SDS disagree, the SRS/SDS win.

## 1. Project

| Item | Value |
|---|---|
| Title | AI-Assisted Multi-Channel Emergency Dispatch System with Three Specialized Agents |
| Institution | Department of Computer Science, Sukkur IBA University |
| Supervisor / Co-supervisor | Dr. Adil Khan / Dr. Zakria Jamali |
| Team | Arjun Kumar (group lead), Khalid Hussain, Sumeet Kumar |
| Repository | `Sumeet-Kumar81/AMCEDS-FYP-Project`, branch `main` |
| Nature | Academic **prototype**, 9 months, one pilot area, simulated data only |

## 2. Purpose

Help an emergency dispatcher (modelled on Rescue 1122) handle reports faster and more safely. The
system takes reports from several channels, understands them, checks whether they look real, finds
repeated reports of the same incident, recommends vehicles and routes, guides the driver and tracks
vehicles live. **The dispatcher always makes the final decision** (SRS §1.4, NFR-S1).

## 3. Scope (SRS §1.4, §1.5)

In scope — features F1–F9:

| Feature | Summary | Use cases |
|---|---|---|
| F1 Report intake | Voice, SMS/text, public web page, mobile app → one Incident Record + reference number | UC-01 |
| F2 Triage Agent | Language, speech-to-text, type, location, victims, severity, confidence | UC-02 |
| F3 Report checking | Trust score/tier from caller history, GPS match, nearby reports, message detail; doubtful → review | UC-03, UC-07 |
| F4 Coordination Agent | Duplicate detection against open incidents; auto-link only at very high confidence | UC-04 |
| F5 Resource Allocation Agent | Vehicle types and counts, rank free vehicles by ETA, route preview, needed + 2 spare | UC-05 |
| F6 Dispatch review | One-screen review, edit, approve, lock vehicles | UC-06, UC-07 |
| F7 Live tracking | Live map, status colours, lost-signal alert | UC-10 |
| F8 Driver app | Assignment alert, accept/decline, navigation, GPS, trip status | UC-08, UC-09 |
| F9 Admin and reports | Login, users/vehicles/hospitals/settings, history and performance | UC-11, UC-12, UC-13 |

Out of scope: real 1122 phone line or Rescue 1122 live systems; real patient/call data; image, video,
social-media or sensor reports; fully automatic dispatch; vehicle tracking hardware; voice stress or
lie detection; hospital beds/records/billing; iOS (Android first).

## 4. Architecture (SDS §4)

Layered **modular monolith** plus a **separate AI worker process** (same codebase, same Docker image,
different command). Do not convert to microservices without approval.

```
Client layer      Public report page (React) · Citizen/Driver mobile app (Android) ·
                  Dispatcher dashboard + Admin panel (React, Leaflet/MapLibre) · SMS/voice simulator
        │ HTTPS REST/JSON + WebSocket (TLS)
API layer         One FastAPI server: auth (JWT), RBAC, routing to services, WebSocket hub
        │
Processing layer  Intake service · AI worker (LangGraph orchestrator → Triage → Coordination →
                  Resource Allocation; deterministic TrustScorer used by Triage) ·
                  Dispatch & Tracking service · Notification service
        │
Data / outside    PostgreSQL 15 + PostGIS · OSRM (OSM pilot-area data) · Geocoder (Nominatim/gazetteer) ·
                  Firebase Cloud Messaging · SMS gateway simulator · LLM via replaceable LLM Gateway
```

Normal report flow (SDS §3.1, §4.3): client submits → API **saves the Incident Record first** and
returns the reference number → AI worker picks up the pending record → speech-to-text and geocoding
if needed → Triage (+ trust score) → Coordination (duplicates) → Resource Allocation (vehicles,
OSRM ETA) → results stored on the same record → API pushes to dashboard over WebSocket → dispatcher
reviews and approves → vehicles locked → driver alerted → driver GPS every ~5 s → live map →
trip status changes → vehicle unlocked when available.

## 5. Technology stack (SDS §4.2; project instructions)

| Area | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (async), asyncpg, GeoAlchemy2, Alembic |
| Database | PostgreSQL 15 + PostGIS (`postgis/postgis:15-3.4` image) |
| AI workflow | LangGraph; LLM accessed only through the LLM Gateway (`backend/app/llm/gateway.py`) |
| Speech-to-text | Whisper / faster-whisper |
| Routing / geocoding | OSRM + OpenStreetMap; Nominatim (pilot gazetteer proposed — D-009) |
| Web | React (Vite), Leaflet or MapLibre with OSM tiles |
| Mobile | Android; React Native per project instructions (SDS says "React Native or Flutter"; repo README says PWA — **D-002 open**) |
| Real-time | WebSocket (FastAPI) |
| Push / SMS | Firebase Cloud Messaging; SMS gateway **simulator** |
| Deployment | Docker Compose: `api`, `ai-worker` (SDS "ai-engine"), `postgres`, `osrm`, `web`, plus `nginx` for TLS |
| Tests | pytest (backend, agents), Postman/HTTP tests (API), Jest (web), Android checklist (mobile) — SDS §8.1 |

No stack change, new framework, paid service or major dependency without a DECISIONS_LOG entry and
approval.

## 6. Safety rules (highest priority — SRS §5.2, Appendix C)

1. **Save before processing.** Every report is committed to the database before any AI step (NFR-P12).
2. **Human decides.** No vehicle is dispatched without an authorised dispatcher approval record (NFR-S1).
3. **Urgent never waits.** High/critical reports are never held for trust checks or duplicate confirmation (NFR-S3).
4. **Careful merging.** Auto-link only at match confidence ≥ 85 %; 60–84 % asks the dispatcher; < 60 % stays separate; no answer = stay separate (NFR-S4, TC-15).
5. **Fake never dispatched.** An incident marked fake cannot be dispatched.
6. **No double dispatch.** A vehicle has at most one open assignment; locking happens only at approval, never at recommendation (NFR-S6, UC-05 post-condition).
7. **Fail-safe / manual mode.** AI, routing or map failure → clear warning, dispatcher continues by hand, no report lost; straight-line ETA labelled "approximate" (NFR-S5, NFR-P13, UC-05 5a).
8. **Honest uncertainty.** Every AI result shows confidence; every report shows trust tier (NFR-S2).
9. **Full record.** Every AI result, dispatcher decision and status change is logged with time and user; the audit log cannot be edited by users (NFR-S9, NFR-C10).
10. **Prototype notice.** "If life is in danger, also call 1122" on the report page and app (NFR-S7).
11. **Simulated data only.** No real patient data, no live Rescue 1122 integration (NFR-C7).

## 7. Business rules (SRS Appendix C — defaults, admin-configurable)

- Trust: start 50, signals in Table 7.3.1 (+15 confirmed-real history; −30 per fake down to −60; +15 GPS ≤ 500 m; −20 GPS > 2 km; +15 one / +25 two-or-more independent nearby reports; +10 real details; −15 vague/joking; −20 device flood). Clamp 0–100. High ≥ 70, Medium 40–69, Low < 40.
- Tier × severity actions: Table 7.3.2 (low tier + high/critical → urgent with warning, dispatch allowed while checking).
- Vehicles: Table 7.3.3 (ambulances = ceil(victims / 2), min 1; fire → ≥ 1 fire truck + ambulances + backup; critical accident → + backup; unknown victims → 1 vehicle + dispatcher check; list = needed + 2 spare).
- Duplicates: same type, ≤ 300 m, ≤ 15 min; ≥ 85 auto-link, 60–84 confirm, < 60 separate. Triage confidence < 60 % → dispatcher must check.
- Timers: assignment response 60 s; lost signal 60 s; on-scene geofence 100 m; GPS every ~5 s; idle logout 30 min; lockout 15 min after 5 wrong passwords.
- New settings apply to new incidents only (UC-12).

## 8. Repository layout (audited 2026-11-19, commit `a0cba20`)

```
backend/            FastAPI app (app/: api, agents, core, llm, models, schemas, services, workers, ws), tests, migrations
db/                 seed/, simulators/, sql/, eval_data/ (all empty placeholders)
docs/               srs-sds/, diagrams/, test-reports/, user-guides/, viva/ (all empty)
frontend/           dashboard/, pwa/ (empty, README only)
infra/              osrm/, gazetteer/, nginx/ (README only)
scripts/dev.sh      docker compose helper
fyp-dispatch/       byte-identical duplicate of the whole tree (D-001)
```

Current implementation state is in **STATUS.md**. The roadmap is **IMPLEMENTATION_PLAN.md**.

## 9. Documentation set

| File | Purpose |
|---|---|
| PROJECT_CONTEXT.md | This file |
| AGENT_RULES.md | Rules every development agent/person follows |
| IMPLEMENTATION_PLAN.md | Batches, agents, tasks, traceability, acceptance criteria |
| STATUS.md | Real current state (verified / unverified / partial / missing) |
| CHANGES.md | Append-only history of every file change |
| DECISIONS_LOG.md | Decisions, conflicts, shared contracts, approval status |
| docs/AI_HANDOFF.md | How the next session/agent continues |
