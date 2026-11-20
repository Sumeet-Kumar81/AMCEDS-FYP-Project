# Part 13 — Risks, conflicts, open decisions and implementation order

This file closes the blueprint. It answers four questions: what can go wrong, where the documents disagree, what the team still has to decide and by when, and in what order the system is built. Nothing here is approved until the team says so (project rule).

## 13.1 Technical and project risks

Probability (P) and impact (I): L = low, M = medium, H = high. Rows R1–R12 come from the approved-for-review implementation plan; R13–R22 are new in this blueprint.

| # | Risk | P | I | Effect | Mitigation | Early warning |
|---|---|---|---|---|---|---|
| R1 | LLM too slow, rate-limited or unavailable | M | H | Misses NFR-P1 (10 s); demo fails | Gateway with two providers plus FakeLLM; 8-s timeout then manual mode; measure latency in Month 2 (A2-17) | p95 triage latency > 6 s in the first benchmark |
| R2 | Urdu / Sindhi / Roman-Urdu understanding and STT quality | H | M | Misses NFR-P7/P8; wrong severity | Few-shot prompts in all scripts, gazetteer aliases, "transcript unclear" flag, text channel as backup, report accuracy per language honestly | WER or type accuracy far under target in the first labelled run |
| R3 | Schema additions (D-004) challenged later | L | H | Rework of models and APIs | D-004 is approved and written into SDS v1.1; contracts are versioned | Any request to change a table after migration 0002 |
| R4 | Mobile framework (D-002) turns out harder than planned | M | H | Driver workflow is on the critical path | Android spike in weeks 1–3 (Expo vs bare decided week 3); citizen mode can fall back to the web page | Spike cannot run background GPS or push by end of week 3 |
| R5 | Android background GPS / FCM restrictions | H | M | Missed positions, late alerts | Foreground service while on duty, WebSocket primary, SMS simulator backup (D-013), real-device tests early | Gaps in GPS trace on a real phone with screen off |
| R6 | OSRM data preparation (memory, extract size) | M | M | No routes | Small pilot-area extract; straight-line fallback already designed and labelled approximate | `osrm-extract` runs out of memory |
| R7 | Concurrency bug in vehicle locking | L | H (safety) | Double dispatch | DB partial unique index, row locks in one transaction, 50-iteration concurrency test (TC-22) | Any run where two approvals both succeed |
| R8 | Duplicate false merges | M | H (safety) | A separate real emergency is hidden | Conservative thresholds, auto-link never changes status, links reversible, tuning with labelled pairs (D-033) | False-merge rate above 5 % in evaluation |
| R9 | Self-signed TLS on Android | M | M | App cannot connect in the demo | D-024 plan, test in Month 8 week 1, rehearse on the demo network | App refuses the demo certificate |
| R10 | Three people editing shared files | M | M | Merge conflicts, broken builds | Ownership table, coordination requests, small pull requests, protected `main` (12_GITHUB_WORKFLOW) | Same file changed in two open PRs |
| R11 | Scope larger than nine months | M | H | Unfinished "should" items | P0/P1/P2 priorities and the scope-cut ladder in `11_ROADMAP_9_MONTHS.md` §11.8 | Month-3 demo misses its milestone |
| R12 | Tools not runnable in some environments (seen in the audit: installs disabled) | M | M | Tests cannot be run | Run tests in Docker and CI; mark results "not verified" honestly | `pytest` cannot import FastAPI |
| R13 | **Duplicate formula cannot reach 85 % (U-1)** | H (proven) | H | TC-13 and NFR-P9 fail by design | Quadratic decay (D-033), already shown to give 93 at TC-13 in the sketch | — |
| R14 | Workload imbalance: Arjun carries AI plus most of the API | H | H | Single point of failure; AI quality suffers | D-034 rebalance (Arjun 23 / Khalid 19 / Sumeet 28 of 70 Batch-1 tasks); weekly check of the plan | Arjun more than one week behind |
| R15 | Calendar unknown (submission and viva dates not in the documents) | H | M | Roadmap cannot be fixed to dates | D-032: team supplies start date, pilot area and viva dates in week 1; roadmap uses weeks 1–36 until then | Still unknown at the end of week 1 |
| R16 | Hardware: LLM + Whisper + OSRM + PostGIS on one demo machine | M | H | Slow or crashing demo | Hosted LLM provider with Ollama as backup; smaller Whisper model; measure memory in Month 2. Figures in `03_TECHNOLOGY.md` are estimates, not measurements | Memory above 80 % in the first full stack run |
| R17 | Low trust wrongly delays a real emergency | L | H (safety) | Delayed help | Policy function proven by a property test: high/critical never goes to `review_queue` (TC-10) | Any test where severity high/critical lands only in the review queue |
| R18 | Library, version or LangGraph API changes after the blueprint | M | L | Code sketches need adaptation | LangGraph wiring is marked NOT VERIFIED; build a one-node graph in week 6 before the full graph | Import or API error on first build |
| R19 | Evaluation data too small or labelled by one person | M | M | Accuracy numbers not credible | 200 reports, double-label 20 %, report counts with the numbers, no claims beyond the data | Two labellers disagree on more than 15 % |
| R20 | Supervisor changes targets after SRS freeze | L | M | Tests chase new numbers | Targets are settings in the evaluation harness (D-017); SRS change request process | — |
| R21 | Data privacy: real names or phone numbers entering the system | L | H | Breaks NFR-C7 | All data simulated; seed and evaluation sets reviewed; secret and personal-data scan in CI (proposed) | Real-looking numbers in a fixture |
| R22 | Demo-day failure (network, laptop, model) | M | H | Bad final impression | Offline demo mode (FakeLLM, local OSRM, recorded voice clips), a recorded demo video, two rehearsals | Rehearsal needs internet |

## 13.2 Conflicts and unresolved requirements

All twelve are detailed in `01_SRS_ANALYSIS.md` §1.8 (U-1…U-12). In one line each:

| ID | Short statement | Proposed resolution | Decision |
|---|---|---|---|
| U-1 | Duplicate formula cannot reach 85 at TC-13 | Quadratic decay | D-033 |
| U-2 | "Other" type: one dispatcher-chosen vehicle vs needed + 2 spare | Show all available vehicles, no automatic type | D-019 |
| U-3 | Unknown victims "1 vehicle" vs fire needing several types | 1 per required type plus check flag | D-019 ext. |
| U-4 | "+2 spare": per type or in total | 2 in total | D-019 ext. |
| U-5 | Low-trust Real decision "goes on to UC-05" | Skip allocation for low tier and low/medium severity until Real | D-021 |
| U-6 | NFR-P1 depends on LLM latency | 8-s timeout then manual mode; benchmark early | R1 |
| U-7 | No similarity formula; "independent report" undefined | Different caller or device; formula in D-033 | D-007/D-033 |
| U-8 | Tier required on every report, but Triage failure removes inputs | Score the non-LLM signals and show "AI unavailable" | D-035 |
| U-9 | Prompt's table list differs from the SDS schema | Map, add nothing | D-031 |
| U-10 | NFR targets need supervisor confirmation | Targets as settings | D-017 |
| U-11 | Sindhi STT weaker | Report honestly; text channel stays | R2 |
| U-12 | FCM needs credentials the team may not have | WebSocket plus SMS simulator | D-013 |

## 13.3 New decisions introduced by this blueprint

These five are **proposals**, not approved (status OPEN). They are recorded in `DECISIONS_LOG.md`.

| ID | Problem | Recommendation | Needed by |
|---|---|---|---|
| **D-031** | The master prompt lists tables that the approved SDS does not have (roles and permissions, drivers, trust scores, AI results, dispatcher decisions, status history) | Keep the SDS schema (11 tables plus the 4 approved additions). Map each prompt table to where the data lives (role column on `users`; driver = `users` with `role='driver'` linked to `vehicles`; trust and AI results as columns and JSONB on `incidents`; dispatcher decisions as `assignments` plus `audit_logs`; status history as audit rows). Add a table only if a measured need appears | Week 1 |
| **D-032** | The documents give no start date, pilot area, submission date or viva date | Team supplies them in week 1; the plan is in weeks 1–36 until then. The pilot area (a district such as Sukkur) decides the OSRM extract, gazetteer and simulated vehicle positions | Week 1 |
| **D-033** | Linear decay in D-007 cannot reach the 85 % auto-link threshold (U-1) | `s_dist = max(0, 1 − (d/300)²)`, `s_time = max(0, 1 − (Δt/15)²)`, weights 0.4 / 0.2 / 0.4 as settings; amends D-007; tune on labelled pairs | Week 9 |
| **D-034** | D-027b gives Arjun about 36 of 70 Batch-1 tasks | Arjun 23 (all AI plus contracts and orchestration), Khalid 19 (web and Android), Sumeet 28 (database, services, admin, analytics, data, tests, deployment); dependency-checked by `tools/schedule_check.py`. Extends D-027b; the team may choose differently | Week 1 |
| **D-035** | A failed Triage leaves the trust scorer without "real details / vague" (U-8) | Score on non-LLM signals (history, GPS distance, nearby reports, flood) and mark the tier "AI unavailable" | Week 4 |

Also recorded as extensions of D-019: U-3 and U-4.

## 13.4 Open decisions by deadline

The full list is in `11_ROADMAP_9_MONTHS.md` §11.9. The first four weeks decide the most:

| By | Decisions |
|---|---|
| Week 1 | D-001, D-001b, D-027b/D-034, D-031, D-032 |
| Week 3 | D-002 sub-choice (Expo vs bare), D-015 |
| Week 4 | D-023, D-009, D-019 (+ extensions), D-035 |
| Week 8 | D-013, D-014, D-022, D-029 |
| Week 9 | D-007/D-033, D-018, D-021 |
| Week 18 | D-016, D-028 |
| Week 28 | D-024, D-025 |
| Week 34 | D-008 (final LLM, with evaluation numbers), D-017 |

A provisional LLM provider is still needed in Month 2 to start the benchmark; it is replaceable by design, so choosing it early costs little.

## 13.5 Implementation order

Build along the life of a report, so each step can be demonstrated. The detailed weekly plan is `11_ROADMAP_9_MONTHS.md` §11.3; this is the logical order and the reason for it.

| Step | What | Why this order | Proof it is done |
|---|---|---|---|
| 0 | Approve the plan, decide week-1 items, clean the repository | Everything else depends on one source tree and one set of documents | Decisions recorded, one tree, v1.1 SRS/SDS in `docs/srs-sds/` |
| 1 | Test harness and CI with a PostGIS service (A1-02) | Nothing is verified today; every later task needs working tests | `pytest -q` passes in Docker and CI |
| 2 | Contracts C-1…C-7 (A1-03, A2-01, A1-04, A1-05) | Three people can then work in parallel without guessing each other's formats | Contracts at v1, signed off |
| 3 | Database: Alembic, models, constraints, migration 0002, settings, audit (A1-06…13) | Every service stores something; the double-dispatch guard lives here | Migration up/down clean; constraint tests pass |
| 4 | Authentication and roles (A1-14, 15) | Every private endpoint needs them | Lockout, idle timeout and role matrix tests pass |
| 5 | Intake: `POST /reports` saves first (A1-16), then voice upload (A1-17) and flood protection (A1-18) | The most important safety rule (save before AI) | TC-01, TC-03, TC-04, TC-50 pass |
| 6 | AI pieces on fakes: LLM gateway, Triage, Trust, policy, similarity, Coordination, routing, Allocation (A2-02…12) | Can be built and tested without the database or the screens | Unit tests pass; truth tables and TC-13…20 pass |
| 7 | Orchestrator and worker, joined to the real database (A2-13, 14, A1-19, B2-01) | First end-to-end: a report becomes a triaged incident | Report to `triaged` row in the database |
| 8 | Dashboard queue, incident review, review queue, live updates (A3-01…09, A1-20…23, 29) | The dispatcher can finally see and judge what the AI did | Demo 2 and Demo 3 |
| 9 | Dispatch approval, locking, drivers (A1-25…28, A3-08, A3-13…18) | The step that moves vehicles; only after everything before it is safe | TC-21, 22, 26…29 pass on a real Android device |
| 10 | Simulated world: SMS, voice, 100 vehicles, scenarios (Batch 4) | Needed for load tests and the demo | 100 simulated vehicles run 30 minutes |
| 11 | Admin, reports, manual-baseline sessions (Batch 5) | Secondary features (SRS "should") | TC-34…37 |
| 12 | Safety validation, hardening and deployment (Batches 6–7) | Proof comes after features, but safety tests are written from the start | TC-44…50 pass; stack starts with one command over HTTPS |
| 13 | Performance and AI evaluation, then final LLM choice (Batch 8) | Measure on the real deployment, tune the thresholds | Numbers recorded against NFR-P targets |
| 14 | Documentation, demo video and acceptance session (Batch 9) | Final deliverables | Supervisor acceptance run |

## 13.6 What would change this order

- If Android turns out hard (R4): move the spike earlier and keep the web driver view as a labelled fallback only with team approval (D-002).
- If the LLM is too slow (R1): build the manual-mode path first and keep the AI optional; the safety design already supports it.
- If a team member is delayed: use the scope-cut ladder (`11_ROADMAP_9_MONTHS.md` §11.8), cutting P2 items first, never a safety rule.

## 13.7 Honest status of this blueprint

| Item | Status |
|---|---|
| The 46 pytest tests for the code sketches in `code_sketches/` | Executed and passed in the writing environment (`10_TESTING.md` §10.9) |
| Mermaid diagrams in this blueprint | Rendered with a Mermaid tool without errors |
| The 36-week schedule | Dependency-checked by `tools/schedule_check.py` (0 violations); effort estimates are judgement, not measurement |
| LangGraph wiring, library versions, hardware figures | **Not verified** (installs and network were off) |
| The two existing backend tests | **Blocked** (no FastAPI in the audit environment) |
| Application code, database, screens, Android app | **Do not exist yet**; the repository still holds the scaffold only |
