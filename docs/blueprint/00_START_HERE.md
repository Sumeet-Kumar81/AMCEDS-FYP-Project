# Blueprint — start here

**Status:** DRAFT for team approval · **Prepared:** 2026-11-20 · **Based on:** SRS v1.1, SDS v1.1 (A-008), IMPLEMENTATION_PLAN v0.2 (70 Batch-1 tasks), DECISIONS_LOG.
**Nothing in this folder is implemented code.** It is the plan. The only code is in `code_sketches/` — design sketches that are tested (45 tests pass) but are **not** part of the application.

## What this blueprint is

Your master prompt asked for a complete implementation blueprint (Parts 1–12) before any coding. This folder is that blueprint. It does **not** replace `planning/IMPLEMENTATION_PLAN.md`; it sits above it:

| Layer | File | Answers |
|---|---|---|
| Why and what | SRS v1.1 | What must the system do? |
| How it is built | SDS v1.1 + this blueprint | Which parts, which tables, which libraries, how do they talk? |
| In what order, by whom | `planning/IMPLEMENTATION_PLAN.md` (70 tasks) + `11_ROADMAP_9_MONTHS.md` | Which task next, who does it, what proves it works? |
| Where we are now | `planning/STATUS.md` | What is really finished? (Today: nothing is implemented or verified.) |

## Reading order (about 90 minutes for the whole team)

1. **This page**, section "The system in five minutes" below.
2. `02_ARCHITECTURE.md` — the picture of the whole system and the life of one report.
3. `06_AI_AGENTS.md` — the three agents and the Trust Scorer (the heart of the project).
4. `11_ROADMAP_9_MONTHS.md` — who does what, month by month.
5. `13_RISKS_AND_ORDER.md` — what can go wrong, open decisions, what we do first.
6. Then the reference files when you start your own work: `04_DATABASE.md`, `05_BACKEND.md`, `07_FRONTEND.md`, `08_MOBILE.md`, `10_TESTING.md`, `12_GITHUB_WORKFLOW.md`.

## File index

| # | File | Your prompt's Part |
|---|---|---|
| 00 | `00_START_HERE.md` | — (guide) |
| 01 | `01_SRS_ANALYSIS.md` | Part 1 SRS analysis, traceability matrix |
| 02 | `02_ARCHITECTURE.md` | Part 2 architecture, workflow, sync/async |
| 03 | `03_TECHNOLOGY.md` | Part 3 technology and libraries |
| 04 | `04_DATABASE.md` | Part 4 database design |
| 05 | `05_BACKEND.md` | Part 5 backend plan, API summary |
| 06 | `06_AI_AGENTS.md` | Part 6 multi-agent implementation |
| 07 | `07_FRONTEND.md` | Part 7 React applications |
| 08 | `08_MOBILE.md` | Part 8 Android app |
| 09 | `09_INTEGRATION.md` | Part 9 integration, end-to-end example |
| 10 | `10_TESTING.md` | Part 10 testing and evaluation |
| 11 | `11_ROADMAP_9_MONTHS.md` | Part 11 nine-month roadmap, team |
| 12 | `12_GITHUB_WORKFLOW.md` | Part 12 GitHub and workflow |
| 13 | `13_RISKS_AND_ORDER.md` | Risks, conflicts, implementation order |
| — | `code_sketches/` | Tested design sketches for Part 6 |

## The system in five minutes

**What it is.** A prototype of an emergency dispatch desk. People report an emergency by voice, SMS, a web page or a phone app. The system turns every report into one standard record, understands it, checks if it looks real, finds repeated reports of the same event, and recommends which vehicles to send. A human dispatcher looks at everything and presses Approve. Only then does a driver get an assignment on an Android phone, and the dispatcher follows the vehicle on a live map.

**The three AI agents.** Each has one job and they do not share code or prompts:

| Agent | One-sentence job | Uses an LLM? |
|---|---|---|
| **Triage** | Read the report: language, type, place, victims, severity, how sure it is. | Yes (through the replaceable LLM Gateway), output always validated |
| **Coordination** | Decide whether this report is about an incident we already have. | No: rules + text similarity |
| **Resource Allocation** | Decide how many of which vehicles, rank free ones by travel time. | No: rules + OSRM routing |

The **Trust Scorer** (is this report probably real?) is a small rule-based module that runs inside the Triage step. It is **not** a fourth agent and uses no LLM (D-012).

**The seven rules that decide design choices** (SRS §5.2). If a design idea breaks one, the idea is wrong:

1. Save the report before any AI step. A report is never lost.
2. AI recommends. The dispatcher approves. Only approval sends a vehicle.
3. Urgent (high/critical) reports never wait for trust or duplicate checks.
4. Merge duplicates automatically only at ≥ 85 % match. In doubt, keep them separate.
5. A vehicle with an open assignment cannot be assigned again. Locking happens at approval, not at recommendation.
6. If AI or routing fails, show a warning and let the dispatcher work by hand.
7. Show confidence on every AI result and a trust tier on every report. Log everything.

**What "done" means.** A task is done only when its code exists, its tests were run, and the result is written in CHANGES.md. Today nothing is done: the repository is a scaffold and the existing two tests have never been shown to pass.

## How we will actually implement it (short version)

1. **Approve the blueprint and the blocking decisions** (D-007 formula, D-008, D-013…D-016, D-021…D-029, plus the new D-031…D-035 in `13_RISKS_AND_ORDER.md`).
2. **Month 1: make the tests run, write the contracts.** Test harness, repository clean-up, shared schemas, API contract, database schema. Nobody builds screens or agents against guessed formats.
3. **Months 2–4: build in parallel behind the contracts, then join.** Backend + database, the three agents against fakes, screens against a labelled mock server. First end-to-end report appears on the dashboard at the end of month 4.
4. **Months 5–6: dispatch and the driver app.** Approve → lock → driver alert → navigation → GPS → live map → trip complete.
5. **Months 7–8: simulators, admin, reports, safety proof, Docker + HTTPS.**
6. **Months 8–9: measure against the SRS targets, fix, document, demonstrate.** Failed targets are reported honestly.

## Honest limits of this blueprint

- It was written from the documents, not from running the system. Library versions and model quality are **not verified**; every external dependency must be checked when its task starts (your prompt's rule: do not assume an API, library or model works).
- Calendar dates are not given because the team's submission and viva dates are not in the documents (D-032, which also fixes the pilot area). The roadmap uses Month 1–9.
- The agent sketches use only the Python standard library and Pydantic. The LangGraph wiring is **not verified** (LangGraph is not installed in this environment and installs are disabled).
