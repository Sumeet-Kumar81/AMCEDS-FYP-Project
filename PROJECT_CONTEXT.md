# PROJECT_CONTEXT.md

> Read this first. It explains the project without relying on any earlier conversation.
> Primary sources of truth: **SRS v1.1** and **SDS v1.1** (revised 2026-11-20 from the Nov 5 SRS and Nov 14 SDS; decision A-008). The clean `.docx` files are committed in `docs/srs-sds/` (path chosen with the B1-A1-02 branch, DECISIONS_LOG D-001b). When this file and the SRS/SDS disagree, the SRS/SDS win. The explanatory layer is `docs/blueprint/` (start with `00_START_HERE.md`).

## 1. Project

| Item | Value |
|---|---|
| Title | AI-Assisted Multi-Channel Emergency Dispatch System with Three Specialized Agents |
| Institution | Department of Computer Science, Sukkur IBA University |
| Supervisor / Co-supervisor | Dr. Adil Khan / Dr. Zakria Jamali |
| Team and roles | **Arjun Kumar** (group lead) — AI & backend; **Khalid Hussain** — frontend & UI/UX; **Sumeet Kumar** — database & technical support (datasets, testing, documentation, deployment). Source: team slide (A-007). Task-level split: D-027b / D-034 (pending) |
| Repository | `Sumeet-Kumar81/AMCEDS-FYP-Project`, branch `main` |
| Nature | Academic **prototype**, 9 months, one pilot area (to be fixed, D-032), simulated data only |

## 2. Purpose

Help an emergency dispatcher (modelled on Rescue 1122) handle reports faster and more safely. The system takes reports from several channels, understands them, checks whether they look real, finds repeated reports of the same incident, recommends vehicles and routes, guides the driver and tracks vehicles live. **The dispatcher always makes the final decision** (SRS §1.4, NFR-S1).

## 3. Scope (SRS §1.4, §1.5)

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

Out of scope: real 1122 phone line or Rescue 1122 live systems; real patient/call data; image, video, social-media or sensor reports; fully automatic dispatch; vehicle tracking hardware; voice stress or lie detection; hospital beds/records/billing; iOS (Android first).

## 4. Architecture (SDS §4)

Layered **modular monolith** plus a **separate AI worker process** (same codebase and image, different command). Do not convert to microservices without approval. The worker receives jobs through a database queue (`pipeline_state`, `SELECT … FOR UPDATE SKIP LOCKED`, `LISTEN/NOTIFY`, D-010); the API saves the record first and the worker does speech-to-text and geocoding (D-011). The Trust Scorer is a rule-based component used by Triage (D-012), **not** a fourth agent.

```
Client layer      Public report page (React) · Citizen/Driver Android app (React Native) ·
                  Dispatcher dashboard + Admin panel (React, Leaflet) · SMS/voice simulators
        │ HTTPS REST/JSON + WebSocket (TLS)
API layer         One FastAPI server: auth (JWT), RBAC, services, WebSocket hub
        │
Processing layer  Intake service · AI worker (LangGraph → Triage (+ TrustScorer) → Coordination →
                  Resource Allocation) · Dispatch & Tracking service · Notification service
        │
Data / outside    PostgreSQL 15 + PostGIS · OSRM (OSM pilot-area data) · Geocoder (gazetteer + Nominatim) ·
                  FCM / SMS simulator · LLM via replaceable LLM Gateway
```

Normal flow: client submits → API **saves the Incident Record first** and returns the reference number → AI worker picks up the record → speech-to-text and geocoding if needed → Triage + trust → Coordination → Resource Allocation (OSRM ETA) → results stored on the record → API pushes to the dashboard → dispatcher approves → vehicles locked → driver alerted → GPS every ~5 s → live map → trip status → vehicle unlocked.

## 5. Technology stack (SDS §4.2)

| Area | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (async), asyncpg, GeoAlchemy2, Alembic |
| Database | PostgreSQL 15 + PostGIS (`postgis/postgis:15-3.4`) |
| AI workflow | LangGraph; LLM only through the LLM Gateway (`backend/app/llm/gateway.py`) |
| Speech-to-text | Whisper / faster-whisper |
| Routing / geocoding | OSRM + OpenStreetMap; gazetteer + Nominatim (D-009 open) |
| Web | React (Vite), Leaflet with OSM tiles |
| Mobile | Android, **React Native** (D-002 approved); Expo vs bare decided after a spike |
| Real-time | WebSocket (FastAPI) |
| Push / SMS | FCM (optional, D-013), SMS gateway **simulator** |
| Deployment | Docker Compose: `api`, `ai-worker`, `postgres`, `osrm`, `web`, `nginx` |
| Tests | pytest, Jest/Vitest (D-015), Android checklist |

No stack change, new framework, paid service or major dependency without a DECISIONS_LOG entry and approval.

## 6. Safety rules (highest priority — SRS §5.2, Appendix C)

1. **Save before processing** (NFR-P12).
2. **Human decides.** No vehicle is dispatched without an authorised dispatcher approval record (NFR-S1).
3. **Urgent never waits.** High/critical reports are never held for trust checks or duplicate confirmation (NFR-S3).
4. **Careful merging.** Auto-link only at match confidence ≥ 85 %; 60–84 % asks the dispatcher; < 60 % stays separate; no answer = stay separate (NFR-S4, TC-15).
5. **Fake never dispatched.**
6. **No double dispatch.** One open assignment per vehicle; locking only at approval, never at recommendation (NFR-S6).
7. **Fail-safe / manual mode.** AI, routing or map failure → clear warning, dispatcher continues by hand, no report lost; straight-line ETA labelled "approximate" (NFR-S5, NFR-P13).
8. **Honest uncertainty.** Every AI result shows confidence; every report shows trust tier (NFR-S2).
9. **Full record.** Every AI result, decision and status change logged with time and user; audit log not editable (NFR-S9, NFR-C10).
10. **Prototype notice.** "If life is in danger, also call 1122" on the report page and app (NFR-S7).
11. **Simulated data only.** No real patient data, no live Rescue 1122 integration (NFR-C7).

## 7. Business rules (SRS Appendix C — defaults, admin-configurable)

- Trust: start 50; signals in Table 7.3.1; clamp 0–100; High ≥ 70, Medium 40–69, Low < 40. Tier × severity actions: Table 7.3.2.
- Vehicles: Table 7.3.3 (ambulances = ceil(victims / 2), min 1; fire → truck + ambulances + backup; critical accident → + backup; unknown victims → 1 vehicle + dispatcher check; list = needed + 2 spare).
- Duplicates: same type, ≤ 300 m, ≤ 15 min; ≥ 85 auto-link, 60–84 confirm, < 60 separate. The scoring formula is **not** given by the SRS; the proposal in D-007 was corrected by D-033 (pending). Triage confidence < 60 % → dispatcher must check.
- Timers: assignment response 60 s; lost signal 60 s; on-scene geofence 100 m; GPS ~5 s; idle logout 30 min; lockout 15 min after 5 wrong passwords.
- New settings apply to new incidents only (UC-12).

## 8. Repository layout (audited 2026-11-19, commit `a0cba20`)

```
backend/   FastAPI app (api, agents, core, llm, models, schemas, services, workers, ws), tests, migrations
db/        seed/, simulators/, sql/, eval_data/ (empty placeholders)
docs/      srs-sds/ (SRS + SDS v1.1 `.docx`), blueprint/ (BP-01), AI_HANDOFF.md; diagrams/, test-reports/, user-guides/, viva/ are empty placeholders (not tracked); the October drafts in the former `Requriments/` folder are no longer on `main`
frontend/  dashboard/, pwa/ (README only)
infra/     osrm/, gazetteer/, nginx/ (README only)
scripts/   dev.sh
fyp-dispatch/  byte-identical duplicate of the tree (D-001)
```

Current implementation state: **STATUS.md**. Roadmap: **IMPLEMENTATION_PLAN.md** + `IMPLEMENTATION_PLAN_UPDATE_v0.3.md` + `docs/blueprint/11_ROADMAP_9_MONTHS.md`.

## 9. Documentation set

| File | Purpose |
|---|---|
| PROJECT_CONTEXT.md | This file |
| AGENT_RULES.md | Rules every development agent/person follows |
| IMPLEMENTATION_PLAN.md (+ update v0.3) | Batches, agents, tasks, traceability, acceptance criteria |
| STATUS.md | Real current state |
| CHANGES.md | Append-only history |
| DECISIONS_LOG.md | Decisions, conflicts, contracts, approval status |
| docs/AI_HANDOFF.md | How the next session continues |
| docs/blueprint/ | 14-file explanation: SRS analysis, architecture, database, backend, AI, frontend, mobile, integration, testing, roadmap, workflow, risks, plus tested design sketches |
