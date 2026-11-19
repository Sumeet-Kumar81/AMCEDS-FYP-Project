# CHANGES.md

Permanent, append-only development history. Newest entries at the bottom. Never edit or delete
earlier entries.

Entry format: date · task ID · purpose · files · what changed · why · DB/API impact · tests and results · limitations.

---

## 2026-11-19 · PLAN-01 · Repository audit and implementation planning (documentation only)

- **Purpose:** Read SRS v1.0 and SDS v1.0, audit the repository at commit `a0cba20`, and produce the batch-based implementation plan with three development agents for Batch 1.
- **Type of work:** Documentation and planning only. **No application source code, models, migrations, APIs, frontend, dependencies, Docker or CI files were changed. No files were deleted or renamed. No database operation was run. Nothing was committed or pushed.**
- **Files created:**
  - `PROJECT_CONTEXT.md`: project purpose, scope, architecture, stack, safety rules, business rules, repo layout.
  - `AGENT_RULES.md`: rules for all agents: session start, file ownership, contracts, safety, conventions, testing, git.
  - `IMPLEMENTATION_PLAN.md`: plan v0.1 with Batch 1 (Agent 1: 34 tasks, Agent 2: 17 tasks, Agent 3: 19 tasks) and Batches 2–9, coordination model, draft endpoint list, WebSocket events, risks and testing strategy.
  - `STATUS.md`: verified current state (nothing verified; tests blocked in the audit environment).
  - `CHANGES.md`: this file.
  - `DECISIONS_LOG.md`: 6 recorded approved-by-source decisions, 29 open decisions (D-001…D-029), 7 shared contracts (C-1…C-7).
  - `docs/AI_HANDOFF.md`: continuation instructions.
- **Files modified:** none existing (none of these documents existed before).
- **DB / API impact:** none.
- **Tests executed:** `cd backend && python3 -m pytest -q` → **blocked**: `ModuleNotFoundError: No module named 'fastapi'` (audit environment had no project dependencies and package installation was disabled). 0 tests executed.
- **Other checks:** `diff -rq --exclude=fyp-dispatch --exclude=.git . fyp-dispatch` → no differences (duplicate tree confirmed).
- **Known limitations:** The plan is a draft pending team/supervisor approval. Endpoint list, schema additions and several rules are proposals recorded as open decisions, not approved requirements. CI run history was not inspected.

---

## 2026-11-19 · PLAN-02 · Team work division updated from the team slide (documentation only)

- **Purpose:** The team supplied slide 4 "Team Roles & Responsibilities" (Arjun Kumar = AI & Backend; Khalid Hussain = Frontend & UI/UX; Sumeet Kumar = Database & Technical Support). Planning documents previously used the README ownership table (Sumeet = frontend, Khalid = database), which contradicts the slide.
- **Type of work:** Documentation and planning only. No source code, config, dependency, database or CI change. `README.md` was **not** edited (it still shows the old ownership table; recorded as a known problem). Nothing committed or pushed.
- **Files modified:**
  - `DECISIONS_LOG.md`: added A-007 (team roles, approved by the team slide); marked D-027 resolved; added D-027b (task-level split, assumptions, workload risk, README update); appended decision-history row.
  - `AGENT_RULES.md`: added §3.1 mapping people to workstreams and file areas.
  - `IMPLEMENTATION_PLAN.md`: version 0.1 → 0.2; added §4.0 team-member mapping.
  - `PROJECT_CONTEXT.md`: team row now lists roles.
  - `STATUS.md`: added known problem about the outdated README ownership table.
  - `docs/AI_HANDOFF.md`: added "Who is who" and person labels on the agent table.
- **DB / API impact:** none.
- **Tests executed:** none (documentation change).
- **Known limitations:** The slide gives roles, not tasks. The task-level split (D-027b) is my proposal and needs team confirmation. The slide does not mention the Android app; it is tentatively assigned to Khalid. Arjun carries the largest share (all AI plus the API).
