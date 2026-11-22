# API_CONTRACT.md — contract C-4 (v1)

**Status:** v1, approved 2026-11-21 by the project developer (sole developer). Task B1-A1-04.
**Sources:** SDS v1.1 Table 4.3 (endpoint list) and Table 4.4 (WebSocket events), decision D-006,
IMPLEMENTATION_PLAN §4.3 (methods for the admin endpoints), contracts C-1, C-2 and C-3.
**Machine-readable contract:** `GET /openapi.json` (FastAPI). The table below and OpenAPI are kept
equal by `backend/tests/api/test_api_contract.py`; a change to either fails the test until both match.

## 1. Rules for every endpoint

- **Prefix:** everything is under `/api/v1`, except `GET /health` (Docker healthcheck), per D-006.
- **Not built yet = 501.** An endpoint that is in the contract but not implemented returns
  `501 Not Implemented` with the error body below. It never returns made-up data.
- **JSON** in and out (`application/json`), except voice upload (`multipart/form-data`) and the
  analytics export (CSV or PDF). Timestamps are ISO 8601 with a time zone (UTC on the wire).
- **Roles:** `P` public, `D` dispatcher, `R` driver, `A` admin, `S` simulator (shared secret), and
  `staff` = D, R or A. Since B1-A1-15 every private route checks them: not signed in → `401`,
  wrong role → `403`, right role → the answer (or `501` until built). The role is read from the
  database on every request. A driver may act only on assignments of the vehicle they drive (`403`
  otherwise, TC-48). `S` routes are not protected yet (D-014 open) and answer `501`.
- **Sessions (C-3, D-023):** send `Authorization: Bearer <access_token>`. Access tokens last 15
  minutes; refresh at `POST /api/v1/auth/refresh` with the refresh token. A session ends at logout,
  after 30 minutes idle (except a driver with an open assignment) or when the account is disabled;
  then every token of that session answers `401` with code `session_ended`.
- **Path ids:** SDS Table 4.3 writes `{id}`; the API names them by what they are
  (`{incident_id}`, `{candidate_id}`, `{assignment_id}`, `{user_id}`, `{vehicle_id}`, `{hospital_id}`).

### 1.1 Error body (every 4xx/5xx response)

```json
{ "code": "not_implemented", "message": "human-readable text", "details": null }
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `bad_request` | The request cannot be understood |
| 401 | `unauthorized`, `invalid_credentials`, `account_locked`, `session_ended` | Not signed in; wrong username or password; locked after too many wrong passwords (TC-32); session ended or token expired |
| 403 | `forbidden` | Signed in but the role may not do this |
| 404 | `not_found` | No such resource (or path) |
| 409 | `conflict` | State conflict, e.g. a vehicle already has an open assignment (dispatch) |
| 422 | `validation_error` | Invalid input. `details` is a list of `{loc, msg, type}`; **the submitted value is never echoed** |
| 429 | `too_many_requests` | Report flood protection (D-022) |
| 501 | `not_implemented` | In the contract, not built yet. `details` = `{"task": "<task id>"}` |
| 503 | `service_unavailable` | The database is down. A report is never given a reference number in this case |

## 2. Shared shapes

| Shape | Defined in | Notes |
|---|---|---|
| `IncidentSummaryOut`, `IncidentDetailOut`, `AssignmentOut` and nested types | C-1, `backend/app/schemas/incident.py` | v1.1 |
| AI results (`TriageResult`, `TrustAssessment`, `AllocationResult`, …) | C-2, `backend/app/schemas/ai.py` | v1; JSON Schemas in `backend/tests/fixtures/contracts/ai/schemas/` |
| `LoginIn`, `RefreshIn`, `TokenOut`, `MeOut`, `AccessTokenClaims`, `UserRole` | C-3, `backend/app/schemas/auth.py` | v1, session design D-023 |
| `ReportIn` | `backend/app/schemas/report.py` | `channel` uses the C-1 vocabulary |
| `DispatchIn`, `VehicleOut` | `backend/app/schemas/dispatch.py` | B1-A1-25: dispatch request; vehicle list for manual dispatch |
| `ErrorBody` | `backend/app/api/errors.py` | §1.1 |

"Defined in task X" below means the body is not fixed yet; the named task defines it and updates
this file and OpenAPI together.

## 3. Endpoints

| Method | Path | Role | Request | Response (success) | Built in |
|---|---|---|---|---|---|
| `GET` | `/health` | P | — | `{api, database}` (worker/OSRM/LLM/geocoder checks added in B1-A1-33) | exists |
| `POST` | `/api/v1/reports` | P | `ReportIn` (channel `web` or `app`; optional `client_request_id`) | `201 ReportAcceptedOut {reference_no, status: "new", received_at}` only after the record is committed; `200` same body for a resend (TC-04); `503` and no reference if it could not be saved | **built** (B1-A1-16) |
| `POST` | `/api/v1/reports/voice` | P | multipart: `audio` (WAV, MP3 or M4A, ≤ 2 min); other fields defined in task | `201`, same as above | B1-A1-17 |
| `POST` | `/api/v1/reports/{reference_no}/confirmation` | P (code) | defined in task | defined in task | B1-A1-24 |
| `POST` | `/api/v1/intake/sms` | S | defined in task (D-014) | defined in task | B4-01 |
| `POST` | `/api/v1/intake/voice` | S | defined in task (D-014) | defined in task | B4-02 |
| `POST` | `/api/v1/auth/login` | P | `LoginIn` | `TokenOut` | B1-A1-14 |
| `POST` | `/api/v1/auth/refresh` | P (refresh token) | `RefreshIn` | `TokenOut`; `401` if the session is idle > 30 min (drivers with an open assignment exempt) | B1-A1-14 |
| `POST` | `/api/v1/auth/logout` | staff | — | `204`; the session ends | B1-A1-14 |
| `GET` | `/api/v1/auth/me` | staff | — | `MeOut` | B1-A1-14 |
| `GET` | `/api/v1/incidents` | D | query: `status` (repeatable), `severity` (repeatable: `critical`, `high`, `medium`, `low`, `unknown`), `include_closed` (default `false`: only new, triaged, needs_check, dispatched, on_scene), `limit` 1–500 (default 100), `offset` | `IncidentSummaryOut[]`: critical → high → unknown → medium → low, then longest-waiting first. Read-only | **built** (B1-A1-20) |
| `GET` | `/api/v1/incidents/{incident_id}` | D | — | `IncidentDetailOut` (current recommendations only, each with `plate_number`, C-1 v1.2); `404 not_found` if missing. Read-only | **built** (B1-A1-20) |
| `PATCH` | `/api/v1/incidents/{incident_id}` | D | type, severity, victims or location; defined in task | `IncidentDetailOut`; recommendation recalculated | B1-A1-21 |
| `GET` | `/api/v1/incidents/{incident_id}/audio` | D | — | the saved audio file | B1-A1-17 |
| `POST` | `/api/v1/duplicate-candidates/{candidate_id}/confirm` | D | defined in task | defined in task | B1-A1-22 |
| `POST` | `/api/v1/duplicate-candidates/{candidate_id}/reject` | D | defined in task | defined in task | B1-A1-22 |
| `GET` | `/api/v1/review-queue` | D | — | `IncidentSummaryOut[]` with `review_reasons` | B1-A1-23 |
| `POST` | `/api/v1/incidents/{incident_id}/confirmation-requests` | D | defined in task | defined in task | B1-A1-24 |
| `POST` | `/api/v1/incidents/{incident_id}/review-decision` | D | `{decision: real \| fake \| need_info, note}`; defined in task | defined in task | B1-A1-23 |
| `POST` | `/api/v1/incidents/{incident_id}/dispatch` | D | `DispatchIn {vehicle_ids[1–10, unique], hospital_id?, override_reason? (≤ 500)}` | `201 AssignmentOut[]` (one `approved` assignment per vehicle; vehicle → `assigned`, incident → `dispatched`; audit `dispatch.approved` with AI suggestion vs choice). `409 vehicle_locked {vehicle_ids, next_best}` (open assignment), `409 vehicle_unavailable {vehicles[{vehicle_id, reason}], next_best}` (not available / no driver / driver off duty), `409 incident_not_dispatchable` (fake or closed), `404` unknown incident, vehicle or hospital. Driver alert not sent yet (B1-A1-30) | **built** (B1-A1-25) |
| `PATCH` | `/api/v1/assignments/{assignment_id}/hospital` | D | defined in task | `AssignmentOut` | B1-A1-26 |
| `POST` | `/api/v1/assignments/{assignment_id}/cancel` | D | defined in task | `AssignmentOut` | B1-A1-26 |
| `GET` | `/api/v1/vehicles` | D | query: `incident_id` (sort by straight-line distance), `type` (repeatable), `available_only` | `VehicleOut[]` (driver, duty, last GPS, `signal_lost`, `has_open_assignment`, `can_dispatch`, approximate `distance_meters`); with `incident_id`: dispatchable first, then nearest. Read-only | **built** (B1-A1-25) |
| `GET` | `/api/v1/fleet/live` | D | — | defined in task | B1-A1-27 (\*) |
| `GET` | `/api/v1/hospitals` | D, R | — | defined in task | B1-A1-26 (\*) |
| `GET` | `/api/v1/routing/route` | D, R | `from`, `to` (lat,lon); defined in task | defined in task; OSRM is never exposed | B1-A2-15 |
| `POST` | `/api/v1/driver/duty/start` | R | — | defined in task | B1-A1-27 |
| `POST` | `/api/v1/driver/duty/end` | R | — | defined in task | B1-A1-27 |
| `GET` | `/api/v1/driver/assignments/current` | R | — | defined in task (contract C-7) | B1-A1-26 |
| `POST` | `/api/v1/driver/assignments/{assignment_id}/accept` | R | — | defined in task (C-7) | B1-A1-26 |
| `POST` | `/api/v1/driver/assignments/{assignment_id}/decline` | R | reason; defined in task | defined in task (C-7) | B1-A1-26 |
| `POST` | `/api/v1/driver/assignments/{assignment_id}/status` | R | on scene, picked up, at hospital, available; defined in task | defined in task (C-7) | B1-A1-26 |
| `POST` | `/api/v1/driver/locations` | R (on duty) | batch of GPS points; defined in task | defined in task | B1-A1-27 |
| `GET` | `/api/v1/admin/users` | A | — | defined in task | B1-A1-31 |
| `POST` | `/api/v1/admin/users` | A | defined in task | `201`, defined in task | B1-A1-31 |
| `PATCH` | `/api/v1/admin/users/{user_id}` | A | defined in task (disable, never delete) | defined in task | B1-A1-31 |
| `GET` | `/api/v1/admin/vehicles` | A | — | defined in task | B1-A1-31 |
| `POST` | `/api/v1/admin/vehicles` | A | defined in task | `201`, defined in task | B1-A1-31 |
| `PATCH` | `/api/v1/admin/vehicles/{vehicle_id}` | A | defined in task | defined in task | B1-A1-31 |
| `DELETE` | `/api/v1/admin/vehicles/{vehicle_id}` | A | — | `204` | B1-A1-31 |
| `GET` | `/api/v1/admin/hospitals` | A | — | defined in task | B1-A1-31 |
| `POST` | `/api/v1/admin/hospitals` | A | defined in task | `201`, defined in task | B1-A1-31 |
| `PATCH` | `/api/v1/admin/hospitals/{hospital_id}` | A | defined in task | defined in task | B1-A1-31 |
| `GET` | `/api/v1/admin/settings` | A | — | defined in task | B1-A1-31 |
| `PUT` | `/api/v1/admin/settings/{key}` | A | defined in task (range-checked; new settings apply to new incidents only) | defined in task | B1-A1-31 |
| `GET` | `/api/v1/admin/audit-logs` | A | — | defined in task (read-only) | B1-A1-31 |
| `GET` | `/api/v1/analytics/incidents` | D, A | period, type, status | defined in task | B1-A1-32 |
| `GET` | `/api/v1/analytics/performance` | D, A | period | defined in task | B1-A1-32 |
| `GET` | `/api/v1/analytics/export` | D, A | `format=csv\|pdf` | CSV or PDF file | B1-A1-32 |

(\*) The plan does not name a task for `GET /fleet/live` or `GET /hospitals`; they are assigned to the
closest task (B1-A1-27 tracking, B1-A1-26 assignments and hospital changes).

**Not in this table:** `GET /api/v1/ws` (WebSocket). WebSocket routes do not appear in OpenAPI; see §4.

## 4. WebSocket events (contract C-5)

`GET /api/v1/ws` (roles D, R; built in B1-A1-29) opens one connection per user. Dispatchers receive the
`dispatchers` channel; each driver receives `driver:<user_id>`. Every message is:

```json
{ "event": "incident.created", "v": 1, "occurred_at": "2026-01-01T09:15:30Z", "data": { } }
```

The models are in `backend/app/schemas/events.py` (`EVENTS` maps each event to its data model and
channel). This table is checked against `EVENTS` by `backend/tests/unit/schemas/test_events.py`.

| Event | Channel | Sent by | `data` |
|---|---|---|---|
| `incident.created` | dispatchers | API (intake) | `IncidentSummaryOut` (C-1) |
| `incident.updated` | dispatchers | API or AI worker | `{incident_id, changed_fields[], pipeline_state}` |
| `incident.ai_failed` | dispatchers | AI worker | `{incident_id, failed_step}` — manual mode |
| `review.item_added` | dispatchers | AI worker or API | `{incident_id, reasons[]}` |
| `review.item_resolved` | dispatchers | AI worker or API | `{incident_id, reasons[]}` |
| `duplicate.candidate` | dispatchers | AI worker | `{incident_id, candidate_incident_id, match_confidence}` |
| `recommendation.ready` | dispatchers | AI worker | `{incident_id, shortage}` (`null` = enough vehicles) |
| `dispatch.approved` | dispatchers | API | `{incident_id, assignments: AssignmentOut[]}` |
| `assignment.new` | driver:&lt;id&gt; | API | `DriverAssignmentOut` (C-7) |
| `assignment.updated` | driver:&lt;id&gt; | API | `DriverAssignmentOut` (C-7) |
| `assignment.accepted` | dispatchers | API | `AssignmentOut` (id, status and times) |
| `assignment.declined` | dispatchers | API | `AssignmentOut` |
| `assignment.timed_out` | dispatchers | API | `AssignmentOut` |
| `assignment.status_changed` | dispatchers | API | `AssignmentOut` |
| `vehicle.position` | dispatchers | API | `{vehicle_id, lat, lon, speed_kmh, recorded_at}` |
| `vehicle.signal_lost` | dispatchers | API | `{vehicle_id, last_position}` |
| `vehicle.signal_restored` | dispatchers | API | `{vehicle_id, last_position}` |
| `system.service_status` | dispatchers | API | `{services: {api, database, ai_worker, osrm, llm, geocoder: up \| down}}` |

**Worker → API (D-010):** the AI worker never talks to clients. It sends `NOTIFY incident_events` with
`{event, incident_id}` (only the six events marked "AI worker" above); the API re-reads the row and
sends the full event. The API wakes the worker with `NOTIFY report_pending`.

## 5. Change log

| Version | Date | Change |
|---|---|---|
| v1 | 2026-11-21 | First version: all 48 endpoints of SDS Table 4.3 (plus `/health`) as 501 stubs; error body; C-3 auth shapes |
| v1.1 | 2026-11-21 | §4 WebSocket events (C-5, B1-A1-05) |
| v1.2 | 2026-11-21 | Auth endpoints built; role checks on every private route (B1-A1-14/15) |
| v1.3 | 2026-11-21 | `POST /api/v1/reports` built (B1-A1-16) |
| v1.4 | 2026-11-22 | `GET /api/v1/incidents` and `GET /api/v1/incidents/{incident_id}` built, read-only (B1-A1-20); C-1 v1.2 adds optional `RecommendationOut.plate_number` |
| v1.5 | 2026-11-22 | `POST /api/v1/incidents/{incident_id}/dispatch` and `GET /api/v1/vehicles` built (B1-A1-25); new shapes `DispatchIn`, `VehicleOut` (`backend/app/schemas/dispatch.py`) |
