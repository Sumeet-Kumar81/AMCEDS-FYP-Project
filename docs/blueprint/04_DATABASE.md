# Part 4 — Database design (PostgreSQL 15 + PostGIS)

Authority: **SDS v1.1 §5** (Tables 5.1–5.15) with the additions approved in D-004 and the vocabularies approved in D-005. This file explains the design and how to build it; it does not add tables. Where your master prompt lists tables that SDS stores differently, see §4.2.

## 4.1 Entity-relationship diagram

```mermaid
erDiagram
  CALLERS ||--o{ INCIDENTS : reports
  INCIDENT_GROUPS ||--o{ INCIDENTS : groups
  USERS ||--o| VEHICLES : drives
  USERS ||--o{ USER_SESSIONS : has
  USERS ||--o{ ASSIGNMENTS : approves
  USERS ||--o{ AUDIT_LOGS : acts
  USERS ||--o{ DUPLICATE_CANDIDATES : decides
  INCIDENTS ||--o{ RECOMMENDATIONS : gets
  INCIDENTS ||--o{ ASSIGNMENTS : leads_to
  INCIDENTS ||--o{ DUPLICATE_CANDIDATES : has
  INCIDENTS ||--o{ CONFIRMATION_REQUESTS : asks
  INCIDENTS ||--o{ AUDIT_LOGS : logged_in
  VEHICLES ||--o{ VEHICLE_LOCATIONS : sends
  VEHICLES ||--o{ RECOMMENDATIONS : suggested
  VEHICLES ||--o{ ASSIGNMENTS : assigned
  HOSPITALS ||--o{ ASSIGNMENTS : destination
  CALLERS {
    bigint caller_id PK
    text phone_number
    text device_id
    int real_count
    int fake_count
    timestamptz flagged_until
  }
  INCIDENTS {
    bigint incident_id PK
    text reference_no UK
    text client_request_id UK
    text channel
    timestamptz received_at
    text original_text
    text audio_ref
    text language
    geometry location
    geometry caller_gps
    text location_text
    text location_source
    text incident_type
    text severity
    int victims_estimate
    float confidence
    int trust_score
    text trust_tier
    bigint group_id FK
    text status
    text pipeline_state
    jsonb ai_details
    jsonb trust_signals
    jsonb allocation_summary
    jsonb settings_snapshot
    text_array review_reasons
  }
  INCIDENT_GROUPS {
    bigint group_id PK
    int report_count
  }
  USERS {
    bigint user_id PK
    text username UK
    text password_hash
    text role
    bool is_active
    int failed_login_count
    timestamptz locked_until
    bool on_duty
  }
  VEHICLES {
    bigint vehicle_id PK
    text plate_number UK
    text vehicle_type
    text status
    bigint driver_id FK
    geometry last_location
    timestamptz last_seen_at
    text station_name
  }
  RECOMMENDATIONS {
    bigint recommendation_id PK
    bigint incident_id FK
    bigint vehicle_id FK
    int rank
    int eta_seconds
    bool eta_is_approximate
    bool is_spare
    int batch_no
    bool is_current
  }
  ASSIGNMENTS {
    bigint assignment_id PK
    bigint incident_id FK
    bigint vehicle_id FK
    bigint approved_by FK
    text status
    bigint hospital_id FK
    timestamptz approved_at
    timestamptz accepted_at
    timestamptz completed_at
  }
  VEHICLE_LOCATIONS {
    bigint location_id PK
    bigint vehicle_id FK
    geometry location
    float speed_kmh
    timestamptz recorded_at
  }
  HOSPITALS {
    bigint hospital_id PK
    text name
    geometry location
    text_array departments
    bool is_active
  }
  AUDIT_LOGS {
    bigint audit_id PK
    timestamptz at
    bigint user_id FK
    bigint incident_id FK
    text action
    jsonb details
  }
  DUPLICATE_CANDIDATES {
    bigint candidate_id PK
    bigint incident_id FK
    bigint candidate_incident_id FK
    float match_confidence
    text decision
  }
  CONFIRMATION_REQUESTS {
    bigint request_id PK
    bigint incident_id FK
    text token_hash
    text response
  }
  USER_SESSIONS {
    text jti PK
    bigint user_id FK
    timestamptz last_activity_at
    timestamptz revoked_at
  }
  SETTINGS {
    text key PK
    jsonb value
  }
```

`settings` and `worker_heartbeats` have no foreign keys and are omitted from the relationship lines. Column lists above show the important columns only; the full lists are SDS Tables 5.1–5.15 and `planning/IMPLEMENTATION_PLAN.md` B1-A1-07…11.

## 4.2 Your prompt's table list mapped to the approved SDS design (decision D-031)

| Prompt asked for | Where it lives in SDS v1.1 | Separate table needed? |
|---|---|---|
| Users | `users` | no |
| Roles and permissions | `users.role` (CHECK: dispatcher, driver, admin); permissions are a role→route matrix in code (`api/deps.py`) with a matrix test | **No** — a permissions table would add admin screens and no new capability for 3 roles |
| Citizens / reporters | `callers` (phone, device, `real_count`, `fake_count`) + optional `incidents.reporter_name` | no |
| Incidents + incident reports | `incidents` (one record per report; the SRS Incident Record) | no |
| Duplicate groups | `incident_groups` + `incidents.group_id` + `duplicate_candidates` | no |
| Vehicles, drivers | `vehicles` (+ `driver_id` → `users`); a driver is a user with role `driver` | no |
| Hospitals | `hospitals` | no |
| Assignments | `assignments` | no |
| GPS tracking history | `vehicle_locations` | no |
| AI processing results | `incidents.ai_details` (JSONB), type/severity/victims/confidence columns, `recommendations`, `incidents.allocation_summary` | no (D-004 option (a): no separate ai_results table) |
| Trust scores | `incidents.trust_score`, `trust_tier`, `trust_signals` (JSONB reasons) | no |
| Dispatcher decisions | `assignments` (approved_by/at) + `audit_logs.details` (AI suggestion vs chosen) + `duplicate_candidates.decided_by` + review decisions in audit | no |
| Incident status history | **Not a table in SDS.** Every status change is an `audit_logs` row (`action='incident.status'` with from/to). History = a query on the audit log | **Proposed: no** (open as D-031: team confirms or asks for a table) |
| Audit logs | `audit_logs` (uneditable) | no |
| System settings | `settings` | no |

**Why not more tables:** D-004 already chose "add columns and two small tables, keep the review queue a query". More tables mean more migrations, more joins and more places for the AI result to be stored twice.

## 4.3 Core table notes (columns beyond the diagram)

| Table | Important points |
|---|---|
| `incidents` | `reference_no` = `INC-` + 6-digit id, set in the same transaction. `original_text` and `audio_ref` are never updated after insert (DB trigger; the worker may set `original_text` **once** from an empty value for voice transcripts). `location` is the resolved point; `caller_gps` is kept separately for the trust check. CHECK constraints: status, type, severity, tier, `confidence` 0–1, `trust_score` 0–100. |
| `callers` | Unique partial indexes on `phone_number` and `device_id` when not null; `flagged_until` set by the rate limiter. |
| `vehicles` | `status` ∈ available, assigned, en_route, on_scene, transporting, at_hospital, offline. `driver_id` unique when not null. |
| `assignments` | `approved_by` NOT NULL. **Partial unique index** `uq_assignment_open_vehicle` on `(vehicle_id) WHERE status IN ('approved','accepted')` — the database refuses a second open assignment. |
| `recommendations` | Separate from assignments on purpose: recommending never locks. `batch_no`/`is_current` keep old batches for audit after a re-run. |
| `audit_logs` | `details` JSONB (so "AI suggested vs dispatcher chose" is queryable). Trigger rejects UPDATE and DELETE. |
| `settings` | Key → JSONB value; every key has default, type, min, max in the settings service; a snapshot is stored on each new incident. |

## 4.4 Types and geography

- Points: `geometry(Point, 4326)` (WGS 84). Distance and radius queries cast to `geography` (`ST_DWithin(location::geography, :pt::geography, :metres)`) so metres are real metres.
- Time: all `timestamptz`, stored UTC; the UI converts to Asia/Karachi.
- Status/enum values: text with CHECK constraints (D-005), not native enums — easier to migrate.
- Money/PII: none stored beyond optional name/phone of simulated callers (NFR-C6, C7).

## 4.5 Indexing strategy

| Index | Purpose |
|---|---|
| GiST on `incidents.location`, `hospitals.location`, `vehicles.last_location` | radius and nearest-vehicle queries (duplicate candidates, allocation) |
| btree `incidents (status, severity)` | dispatcher queue |
| btree `incidents (incident_type, received_at)` | duplicate candidate query and reports |
| partial btree `incidents (pipeline_state, received_at) WHERE pipeline_state IN ('pending','reallocate')` | worker `claim_next` |
| btree `vehicle_locations (vehicle_id, recorded_at DESC)` | latest position and history |
| unique `incidents (reference_no)`, `incidents (client_request_id)` | caller lookup, idempotency (TC-04) |
| partial unique `assignments (vehicle_id) WHERE status IN ('approved','accepted')` | NFR-S6 |
| btree `audit_logs (incident_id, at)`, `(user_id, at)` | history views |
| btree `recommendations (incident_id) WHERE is_current` | current recommendations |

Rule: every index is added **with the query that needs it**, and `EXPLAIN` output for the spatial ones is pasted into CHANGES.md (task B1-A1-09).

## 4.6 Migration plan (Alembic)

| Revision | Content | Task |
|---|---|---|
| `0001_enable_postgis` | `CREATE EXTENSION postgis` | B1-A1-06 |
| `0002_initial_schema` | all tables, CHECKs, indexes, audit trigger, original-text trigger | B1-A1-11 |
| `0003_seed_settings` | default settings rows | B1-A1-12 |
| `0004+` | extra columns added with the feature that needs them (D-004 staged: Milestone-1 columns first) | per task |

Rules: one migration per task; each tested with `upgrade head` then `downgrade base` on the test database; never edit an applied migration; no schema change without approval (project rule).

## 4.7 Data used for development

| Data | Where | Size | Notes |
|---|---|---|---|
| Users, vehicles (30 → 100), hospitals (8), stations as text | `db/seed/` | small / full modes | All labelled SIMULATED; passwords from env |
| Gazetteer landmarks | `infra/gazetteer/landmarks.csv` | 50–100 | EN/Urdu/Roman-Urdu aliases |
| Labelled reports | `db/eval_data/reports.jsonl` | ≥ 200 | EN, Urdu script, Roman-Urdu, Sindhi |
| Duplicate groups | `db/eval_data/duplicate_groups.jsonl` | ≥ 50 groups incl. near-miss non-duplicates | Needed to tune D-033 |
| Voice clips | `db/eval_data/voice/` | team-recorded | Not committed if large |
