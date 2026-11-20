# Part 7 — Frontend development (React web applications)

Authority: SDS v1.1 §7 (screen inventory) and SRS UC-06, UC-07, UC-10, UC-12, UC-13. Owner: Khalid (Agent 3). Rule: **only contracted APIs** (C-1…C-5) and generated types; AI output always labelled as a recommendation; dispatch always needs an explicit dispatcher action. No hardcoded arrays for finished features; any temporary mock data carries a visible **MOCK DATA** banner and is removed before the screen is marked done.

## 7.1 Applications and folders

```
frontend/
  dashboard/   React + TypeScript + Vite — dispatcher + admin (+ dev-only Channel Simulator page, SIMULATED)
  pwa/         React + TypeScript + Vite — public report page (D-002: may be renamed public-report)
  shared/      typed API client (generated from /openapi.json), WebSocket client, UI kit, i18n (en, ur)
mobile/        React Native (see 08)
```

Today both web folders hold only `.gitkeep`.

## 7.2 Public reporting application (UC-01)

| Page | Contents | Rules |
|---|---|---|
| `/` Report | Notice **"If life is in danger, also call 1122"** (always visible, NFR-S7/TC-47); description box; Record voice (≤ 2 min, preview, re-record); location: *Use my location* or type address/landmark; optional name and phone; **Send** | Collect only what NFR-C6 allows; works at 360 px width; English/Urdu toggle with RTL for Urdu; Sindhi accepted as free text |
| `/sent` Confirmation | Reference number `INC-000123`, "your report was saved", reminder to call 1122 if in danger | Shown only after the API returns 201 (i.e. after commit) |
| Error states | Validation messages; **429** "too many reports, please call 1122"; **503** "could not save your report — call 1122 now" | Never show a reference number on failure |

Technical points: `navigator.geolocation` (denied → ask for landmark; none → still sendable, location "unknown", TC-03); `MediaRecorder` for voice with a 120-s stop; `client_request_id` (UUID) generated once per submission so a retry is safe (TC-04); `POST /reports` or `/reports/voice`.

## 7.3 Dispatcher dashboard (UC-06, UC-07, UC-10)

| Route | Screen | What it shows | API / events |
|---|---|---|---|
| `/login` | Login | username/password, lockout message | `POST /auth/login` |
| `/` | **Dashboard overview** | counts by status/severity, service banner, newest critical items, link to queue and map | `GET /incidents`, `system.service_status` |
| `/queue` | **Incident queue** | cards sorted by severity then time: severity colour + text, location, time, trust tier, flags (urgent-with-warning, possible duplicate, multiple reports, low confidence, AI failed); sound/visual cue for new critical | `GET /incidents`, `incident.created/updated` |
| `/incidents/:id` | **Incident review + dispatch approval** (one screen, SDS §7.2 items 1–7) | original report exactly as sent + audio player + transcript with "unclear" warning; AI type, severity, victims, location **each with a confidence meter**; trust tier + score + reasons; review reasons; duplicate warning with *Confirm* / *Keep separate*; map; ranked vehicles with ETA (and **approximate** tag), route preview, shortage warning; select/deselect vehicles; hospital suggestion; **Approve Dispatch** → summary → **Confirm** (3 clicks: open incident, Approve, Confirm; NFR-P14); *Edit details*; *Mark as fake* | `GET /incidents/{id}`, `PATCH`, duplicate confirm/reject, `POST …/dispatch`, `recommendation.ready` |
| `/review` | **Review queue** | doubtful reports with reasons; *Ask caller to confirm* (shows call-back number), reply when it arrives; *Real* / *Fake* (confirmation dialog) / *Need more information*; urgent items show "dispatch allowed while checking" | `GET /review-queue`, confirmation-requests, review-decision |
| `/map` | **Live map** | vehicles by status colour, signal-lost in grey at last position, incidents, hospitals, dashed route of en-route vehicles, filters (type, status, area), vehicle detail panel, alerts | `GET /fleet/live`, `vehicle.position`, `vehicle.signal_lost` |
| `/history` | **Incident history** | filters (period, type, status), timeline received → triaged → approved → arrived | `GET /analytics/incidents` |
| `/performance` | **Performance reports** | four measures, AI-assisted vs manual, Export CSV, empty-period message | `GET /analytics/performance`, `/export` |
| `/admin/*` | **Administration** (admin role) | Users, Vehicles, Hospitals, Settings, Audit Log | `/admin/*` |

Manual mode: if `system.service_status` says AI or routing is down, a banner appears; screens still work from REST data; the approval panel lists available vehicles nearest-first (`GET /vehicles`) labelled "manual dispatch".

## 7.4 Shared UI rules (SDS §7.6)

| Component | Rule |
|---|---|
| `SeverityBadge` | red critical, orange high, blue medium, green low, **plus text** (colour is never the only cue) |
| `ConfidenceMeter` | percentage next to every AI value; below the threshold shows "dispatcher must check" |
| `TrustBadge` | tier + score on every report |
| `AiRecommendationLabel` | "AI recommendation — dispatcher decides" on suggestion panels |
| `ApproximateEtaTag` | whenever `eta_is_approximate` |
| `ServiceStatusBanner` | from `system.service_status` |
| `LoadingState`, `EmptyState`, `ErrorState` | every list/detail screen has all three |
| Edited vs AI values | shown distinctly; AI value never overwritten in the UI |

## 7.5 Component and state structure

```
src/
  app/            router, providers, layout, role guards
  auth/           login, token store (memory), idle timer (warn at 28 min), guards
  api/            generated client wrapper (auth header, refresh on 401, error mapping)
  realtime/       one WebSocket per session, reconnect + REST resync, event → query-cache updates
  features/
    queue/ incident/ dispatch/ review/ map/ reports/ admin/ report-form/
  ui/             severity, trust, confidence, banners, empty/loading/error
  i18n/           en.json, ur.json
```

State: server data in **TanStack Query** (proposed, D-015) invalidated by WebSocket events; a small store only for UI state (selected vehicles, filters). Tokens kept in memory with refresh, not `localStorage`.

## 7.6 API integration strategy

1. Backend publishes `/openapi.json` in Phase 1A (route stubs return 501) → `openapi-typescript` generates types → screens compile against the real contract from day one.
2. A **mock mode** serves only the contract fixtures (`backend/tests/fixtures/contracts/`) and shows MOCK DATA; each screen switches to the live API when its endpoint passes its tests (Batch 2, task B2-03).
3. After a WebSocket reconnect the client refetches via REST, then continues with events (events are hints).
4. 409 `vehicle_locked` → warning + next-best vehicle; 503 → service banner; 401 → login.

## 7.7 Frontend testing

Component tests (Jest or Vitest + React Testing Library per D-015): severity colours, threshold label, RTL for Urdu, ordering of the queue, duplicate actions, click count = 3, no dispatch without Confirm, manual-mode list, role guards, idle logout with fake timers. Performance check: 100 live markers updating every 5 s stay responsive. Browsers: latest Chrome, Edge, Firefox (TC-52).

## 7.8 Build order

B1-A3-01 scaffolding + client → 02 UI kit → 05 WebSocket client → 04 auth → 03 public page → 06 queue → 07 review → 08 approval → 09 review queue → 10 map → 11 admin → 12 reports → 19 test suites. Each screen is built against fixtures first and joined to the real API in Batches 2–3.
