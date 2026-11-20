# IMPLEMENTATION_PLAN — update v0.3 (applies on top of IMPLEMENTATION_PLAN.md v0.2)

**Date:** 2026-11-20 · **Status:** proposal, pending team approval. The v0.2 task text (B1-A1-01 … B9-09) stays valid except for the changes below. Merge this file into `IMPLEMENTATION_PLAN.md` when the team approves, then delete it.

## 1. Sources changed
- Authoritative documents are now **SRS v1.1 and SDS v1.1** (A-008). Wherever v0.2 says "SRS v1.0 / SDS v1.0" or cites a v1.0 table number, use the v1.1 section or table number (D-003).
- Approved on 2026-11-20 and now written into SDS v1.1: D-002 (React Native), D-004 (schema additions, new Tables 5.12–5.15), D-005 (status vocabularies), D-006 (API list, Tables 4.3 and 4.4), D-010, D-011, D-012, D-020. The task text that says "needs D-004/D-005/D-006" is satisfied.

## 2. New reference documents
`docs/blueprint/` is the explanatory layer: `00_START_HERE` (reading order), `01` SRS analysis and traceability, `02` architecture, `03` technology, `04` database, `05` backend, `06` AI agents (with tested sketches), `07` frontend, `08` mobile, `09` integration, `10` testing, `11` nine-month roadmap, `12` GitHub workflow, `13` risks and order.

## 3. Schedule
`11_ROADMAP_9_MONTHS.md` maps every Batch-1 task to a week (1–36) and a person; dependency-checked by `docs/blueprint/tools/schedule_check.py`. It replaces the "phase" ordering of v0.2 inside Batch 1 only; tasks, files and acceptance criteria are unchanged.

## 4. Plan clarifications
| ID | Change to v0.2 |
|---|---|
| P-1 | `B1-A2-13` orchestrator is delivered in two steps: text path first (week 13), STT and hospital nodes added in week 24 |
| P-2 | `B1-A2-17` evaluation harness v1 uses text metrics (week 18); word-error-rate added when STT lands |
| P-3 | Order A1-29 → A1-30 → A1-24; TC-12 end to end waits for week 16–17 |

## 5. Proposed changes needing approval (new decisions)
| ID | Effect on the plan |
|---|---|
| D-031 | No extra tables beyond D-004; the prompt's table list is mapped to the SDS schema |
| D-032 | Calendar dates, pilot area and viva dates supplied in week 1 |
| D-033 | `B1-A2-08`/`B1-A2-09`: quadratic decay in the duplicate score (amends D-007) so TC-13 can pass |
| D-034 | Task split Arjun 23 / Khalid 19 / Sumeet 28, replacing the D-027b counts in §4.0 of the plan |
| D-035 | `B1-A2-06`/`B1-A2-13`: when Triage fails, trust is scored on non-LLM signals and marked "AI unavailable" |
| D-019 extensions | Unknown victims = 1 vehicle per required type; "+2 spare" is two in total |

## 6. Risks
`13_RISKS_AND_ORDER.md` §13.1 extends the v0.2 risk table (R1–R12) with R13–R22.
