# Part 10 — Testing and evaluation

Rules from the project instructions: every task has tests; results are recorded with the **command, date, environment and one of passed / failed / blocked / skipped / not executed**; nothing is reported as passed unless it was run. SDS §8 test cases **TC-01…TC-52** are the basis of system verification. A task is complete only when its required tests were run (STATUS.md rule).

## 10.1 Test levels

| Level | Tool | Location | Runs | Covers |
|---|---|---|---|---|
| Unit (backend, agents) | pytest | `backend/tests/unit/` | every task, CI | services, scorer, policy, scoring, allocation, schemas, FakeLLM triage, pipeline logic |
| API | pytest + httpx `AsyncClient` | `backend/tests/api/` | every backend task, CI | each endpoint, validation, 401/403 matrix, error codes, TC-01, 03, 04, 05, 21–25, 32–37, 46–50 |
| Database | pytest on PostGIS test DB (`@pytest.mark.db`) | `backend/tests/integration/` | CI with PostGIS service | constraints, migrations up/down, triggers, spatial queries, partial unique index, claim concurrency |
| Integration (worker) | pytest | `backend/tests/integration/` | Batch 2 | real `pipeline_store`, real OSRM container, FakeLLM end to end |
| Agent evaluation | `tests/ai_eval/run_eval.py` | labelled sets in `db/eval_data/` | Month 2, Batch 8 | accuracy, confusion matrices, latency, duplicate recall, WER, ETA error |
| Frontend | Jest/Vitest + React Testing Library | `frontend/*/src/**/*.test.tsx` | every UI task, CI | components, flows, role guards, i18n/RTL |
| Mobile | unit tests + device checklist | `mobile/`, `docs/test-reports/mobile_checklist.md` | driver tasks, B3 | offline queue, geofence, GPS only on duty; real-device TCs |
| Performance | asyncio load script or `locust` (needs D-entry) + simulators | `tests/perf/` | Batch 8 | NFR-P1…P6 |
| Security | pytest + manual checks | `backend/tests/api/test_rbac_matrix.py`, security checklist | Batch 7 | NFR-C1…C11 |
| End to end | scenario runner + UI walkthrough | `db/simulators/scenarios/` | Batches 2–6, 9 | TC-01…52 through the real stack |
| Acceptance | supervisor demo | prepared scenarios | Batch 9 | SDS §8.1 |

## 10.2 Existing tests today

`backend/tests/api/test_health.py` has 2 tests. They **could not run** in the audit environment (FastAPI not installed, installs disabled): status **BLOCKED**. First verified results come from task B1-A1-02 (Docker/CI).

## 10.3 Safety tests that must never be removed

| Rule | Test |
|---|---|
| Save before AI (NFR-P12) | API test with the worker absent: report saved with `pending`, reference returned; DB-down → 503 and no reference |
| Human decides (NFR-S1) | Dispatch endpoint without token/with driver token → 401/403 and zero assignment rows (TC-46); agents have no write path to assignments (read-only fake) |
| Urgent never waits (NFR-S3) | Policy property test + TC-10 + critical low-trust incident is dispatchable |
| Careful merging (NFR-S4) | Boundary tests 84.9 / 85.0; unanswered possible duplicate stays separate (TC-15); link does not change status |
| No double dispatch (NFR-S6) | Partial-unique-index test + 50-iteration concurrent approval test (TC-22) |
| Fake never dispatched | Dispatch on `fake` incident → 409; review-decision fake on open assignment → 409 |
| Fail-safe (NFR-S5, P13) | Stop worker/LLM/OSRM → warning and manual dispatch still work (TC-44, TC-45) |
| Audit complete (NFR-S9) | Script checks every AI result, decision and status change has an audit row with user/time; UPDATE/DELETE on `audit_logs` rejected |

## 10.4 Mapping SDS test cases to levels

| TCs | Level | Batch |
|---|---|---|
| 01–05 intake | API + UI | B1, B2 |
| 06–08 triage | agent unit (FakeLLM) now; real model in eval | B1, B2, B8 |
| 09–12 trust | scorer unit + API + e2e | B1, B2 |
| 13–15 duplicates | agent unit + e2e | B1, B2 |
| 16–20 allocation | agent unit + OSRM integration | B1, B2 |
| 21–25 dispatch/review | API + concurrency + UI | B1, B3 |
| 26–29 driver | API + device | B3 |
| 30–31 live map | API + UI + simulator | B3 |
| 32–37 auth/admin/reports | API + UI | B1, B5 |
| 38–43 performance | load/latency scripts | B8 |
| 44–45 resilience | e2e fault injection | B2, B6 |
| 46–50 safety/security | API + manual | B6, B7 |
| 51–52 usability/compatibility | click count + browser/Android matrix | B8 |

## 10.5 How each SRS target is measured and documented

| Target | Measurement method | Data | Pass rule | Record |
|---|---|---|---|---|
| Text triage within 10 s (P1) | script submits 50 text reports one at a time; timestamps `received_at` → first `incident.updated` carrying triage + recommendation on the dashboard WebSocket | 50 simulated reports | ≥ 95 % ≤ 10 s; report p50/p95/max and LLM provider | `docs/test-reports/perf_text_latency.md` |
| Voice within 20 s (P2) | 20 clips of 60 s; time to triage | team-recorded clips | ≥ 95 % ≤ 20 s | `perf_voice_latency.md` |
| Recommendation ≤ 5 s (P3) | stage timer from `save_triage` to `recommendation.ready` | same runs | ≤ 5 s | worker logs |
| Map update ≤ 5 s (P4) | simulator sends point with `recorded_at`; browser logs arrival time | 100 vehicles | ≤ 5 s from send | `perf_gps.md` |
| Driver notification ≤ 5 s (P5) | approval time → app receive time (clock-synced device) | 20 dispatches | ≤ 5 s | `perf_notify.md` |
| 50 simultaneous reports + 100 vehicles (P6) | load script + vehicle simulator for 30 min | 50 parallel submissions | none lost, UI responsive, no errors | `perf_capacity.md` |
| Incident type ≥ 85 % (P7) | `run_eval.py` on labelled reports (≥ 200, EN/Urdu/Roman-Urdu/Sindhi) | `reports.jsonl` | accuracy overall and per language, confusion matrix | `ai_eval_<date>.md` |
| Severity ≥ 80 % (P8) | same | same | accuracy; off-by-one analysis | same |
| Duplicates ≥ 80 % found, ≤ 5 % wrong merges (P9) | pairs from `duplicate_groups.jsonl` including near-miss non-duplicates | ≥ 50 groups | recall and wrong-merge rate; tune weights/decay on a **tuning split**, report on a **held-out split** | same |
| ETA within 20 % (P10) | OSRM prediction at dispatch vs simulated travel time (simulator follows OSRM geometry at the speed model) | 50 trips | median and p90 error | `perf_eta.md` |
| Availability ≥ 99 % (P11) | `/health` polled every minute during all test/demo hours | uptime log | ≥ 99 % | `perf_uptime.md` |
| Click count ≤ 3 (P14) | UI test + manual count | recommended dispatch | ≤ 3 | test report |
| Browsers/Android (P17) | matrix run | Chrome, Edge, Firefox; Android 9+ | all features work | `compat_matrix.md` |

**Honesty rules:** every report states the machine (CPU, RAM), the LLM provider/model and version, the dataset version and the date. A target that is missed is reported as missed, with analysis and the change made — never hidden or re-defined. NFR targets are still awaiting supervisor confirmation (D-017).

## 10.6 Performance test design

- Warm-up run first; then measured runs; report percentiles, not averages only.
- Same hardware as the demo configuration (Docker Compose, TLS on).
- Separate **LLM time**, **STT time**, **OSRM time** and **database time** per stage using the worker's stage timers so bottlenecks are visible.
- Capacity test increases load in steps (10 → 25 → 50 reports) to find the knee.

## 10.7 Security test checklist (Batch 7)

RBAC matrix over every route; brute-force lock (TC-32); injection text saved harmlessly (TC-50); HTTPS only (TC-49); CORS restricted; rate limit (TC-05); no secrets in repo (scan) or logs; passwords hashed; audit table immutable; driver GPS refused off duty; JWT tampering and expired token rejected; file upload limits; dependency audit.

## 10.8 Reporting format (every test report)

`Task ID · date · commit · environment · command · result (passed/failed/blocked/skipped/not executed) · counts · notes`. CHANGES.md carries the short form for each task; long reports go to `docs/test-reports/`.

## 10.9 Verified now: the design sketches

| Date | Command | Environment | Result |
|---|---|---|---|
| 2026-11-20 | `cd docs/blueprint/code_sketches && python -m pytest -q -p no:cacheprovider` | Python 3.13, pydantic 2.13, pytest 9.1, no network | **PASSED — 46 tests, 0 failed.** Covers scorer (Table 7.3.1), policy truth table, duplicate scoring incl. TC-13/14, vehicle counts incl. TC-16–19, triage validation incl. TC-06–08, pipeline order incl. critical low-trust still allocated |
| 2026-11-20 | `scripts/check_mermaid.sh docs/blueprint/*.md` (mermaid-cli 11.16) | sandbox | **PASSED** — every Mermaid block renders |

These prove the *design logic*. They do **not** verify any application code, the LangGraph wiring, the database, the API or any screen — none of which exists yet.
