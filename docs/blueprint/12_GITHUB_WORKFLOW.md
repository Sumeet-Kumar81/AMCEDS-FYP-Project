# Part 12 — GitHub and development workflow

Repository: `Sumeet-Kumar81/AMCEDS-FYP-Project`, branch `main` (baseline `a0cba20`). Existing: `.github/workflows/ci.yml` (pytest on Python 3.11, no DB service, no frontend job — not yet verified), `.gitignore`, `.env.example`, `docker-compose.yml` (postgres + api), `scripts/dev.sh`. **Project rule: no automatic commits or pushes.** An AI agent (or a person) shows the changed files, test results and a summary first; the team decides when to commit and push.

## 12.1 Repository structure (monorepo, one repository)

A monorepo fits three people and one deployable system: one pull request can change a schema, its API and its screen together. The structure already exists; this is the target:

```
AMCEDS-FYP-Project/
├─ README.md                    what it is, how to run, ownership
├─ PROJECT_CONTEXT.md  IMPLEMENTATION_PLAN.md  STATUS.md  CHANGES.md  DECISIONS_LOG.md  AGENT_RULES.md
│                               (today these live in the Claude Project under planning/; D-001b: commit to the repo root)
├─ docs/
│  ├─ srs-sds/                  SRS v1.1 + SDS v1.1 (.docx) — the sources of truth (replace docs/Requriments/ drafts)
│  ├─ blueprint/                this blueprint
│  ├─ AI_HANDOFF.md  API_CONTRACT.md
│  ├─ diagrams/  test-reports/  user-guides/  viva/
├─ backend/  app/{api,agents,core,llm,integrations,models,schemas,services,workers,ws}  migrations/  tests/{unit,api,integration,ai_eval}
├─ frontend/  dashboard/  pwa/ (public report)  shared/
├─ mobile/                      React Native app (D-002)
├─ db/  seed/  sql/  simulators/  eval_data/
├─ infra/  osrm/  gazetteer/  nginx/
├─ scripts/  dev.sh
├─ docker-compose.yml  .env.example  .gitignore
└─ .github/  workflows/ci.yml  pull_request_template.md  CODEOWNERS
```

Cleanup before work starts: remove the byte-identical `fyp-dispatch/` copy (D-001, needs explicit approval) and place the v1.1 SRS/SDS in `docs/srs-sds/` (D-001b). Note: PR #3 currently carries the October drafts and must carry the v1.1 files.

## 12.2 Branching strategy

Small team, short tasks → **trunk-based with short-lived branches**, not Git-flow.

| Branch | Rule |
|---|---|
| `main` | Always working; protected: pull request required, CI must pass, one review by a different teammate, no force-push, no direct commits |
| `feature/<task-id>-<slug>` | One task per branch, e.g. `feature/A1-16-intake-service`. Lives days, not weeks; rebase on `main` before opening the PR |
| `fix/<slug>` | Bug fixes |
| `docs/<slug>` | Documentation-only changes |
| `release/demo-N` (tag `demo-N`) | A tag (or branch) cut before each supervisor demo so the demo state is reproducible |

Never discard another person's uncommitted work, reset shared history, or force-push (project rule).

## 12.3 Commit convention

[Conventional Commits](https://www.conventionalcommits.org/) with the task ID:

```
<type>(<scope>): <summary> [<task-id>]

type  : feat | fix | docs | test | refactor | chore | ci | build
scope : backend | agents | db | api | frontend | mobile | infra | docs
example: feat(api): save report before AI processing [B1-A1-16]
```

One logical change per commit; the message says *why*, not only *what*. No secrets, no `.env`, no generated audio or model files.

## 12.4 Pull-request workflow

1. Take one task from `IMPLEMENTATION_PLAN.md`; read its SRS/SDS sections, STATUS.md and the latest CHANGES.md entries.
2. Write the intended change (files, DB impact, API impact, tests) in the PR description **before** coding if it touches a contract.
3. Implement the smallest testable unit; run the tests locally in Docker.
4. Update, in the same PR: `CHANGES.md` entry (date, task ID, files, tests and **actual results**), `STATUS.md`, and `DECISIONS_LOG.md` / `API_CONTRACT.md` if a contract moved.
5. Open the PR using the template below; CI must be green; a different teammate reviews.
6. Merge (squash) only after review; delete the branch.

Pull-request template (`.github/pull_request_template.md`):

```markdown
## Task
ID: B1-A?-??   SRS/SDS refs: UC-?? / NFR-?? / SDS §?

## What changed and why

## Safety rules touched (tick if affected, explain)
- [ ] save-before-AI  - [ ] human approval  - [ ] urgent never waits  - [ ] careful merging
- [ ] one open assignment  - [ ] manual mode  - [ ] audit logging

## Database / API impact
(migration name, endpoints, contract version)

## Tests
Command: `…`   Result: passed / failed / blocked / not run (counts)

## Docs updated
- [ ] CHANGES.md  - [ ] STATUS.md  - [ ] DECISIONS_LOG / API_CONTRACT (if needed)

## Not done / limitations
```

`CODEOWNERS` (proposal, follows file ownership in AGENT_RULES.md): `backend/app/agents/**`, `backend/app/llm/**`, `backend/app/workers/**`, `backend/app/integrations/**` → Arjun; `backend/app/{models,services}/**`, `backend/migrations/**`, `db/**` → Sumeet; `frontend/**`, `mobile/**` → Khalid; shared files (`requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/**`) → all three.

## 12.5 Shared files and coordination requests

`backend/requirements.txt`, `docker-compose.yml`, `.env.example`, `.github/**`, `README.md`, root docs change only through a **Coordination Request** in `DECISIONS_LOG.md` §4, so three people do not edit them at once. Any new dependency needs a D-entry first (project rule).

## 12.6 Environment configuration and `.env` management

| Rule | Detail |
|---|---|
| Template | `.env.example` is committed with **placeholder** values and a comment per variable; the real `.env` is git-ignored (already in `.gitignore`) |
| Variables (names only) | `ENV` (dev/test/prod), `DATABASE_URL`, `JWT_SECRET`, `LLM_PROVIDER`, `LLM_API_KEY`, `OLLAMA_URL`, `OSRM_URL`, `NOMINATIM_URL`, `AUDIO_STORE_DIR`, `SIM_SHARED_SECRET`, `FCM_CREDENTIALS_PATH`, `SEED_*_PASSWORD` |
| Secrets | Never in code, docs, logs, screenshots or commits (NFR-C9). Startup refuses the default JWT secret when `ENV` is not `dev` |
| Per-environment | `.env` (local), `.env.test` (CI/test DB), compose `environment:` for containers; the Android app takes its API URL from a build-time config, not from code |
| Checks | CI step runs a secret scanner (e.g. gitleaks, needs a D-entry); pre-commit hook blocks `.env` |
| Sharing secrets | Team password manager or a private channel; **never** the repository or the Claude Project |

## 12.7 Docker configuration

| Item | Plan |
|---|---|
| Today | `postgres` (`postgis/postgis:15-3.4`) + `api` (`python:3.11-slim`) |
| Add | `ai-worker` (same image, `command: python -m app.workers.ai_worker`) in Batch 2; `osrm` (data from `infra/osrm/prepare.sh`), `nginx` (TLS), `web` (static builds), optional `ollama` by Batch 7 |
| Practices | healthchecks, `restart: unless-stopped`, named volumes for database, audio and OSRM data, the same image for `api` and `ai-worker` so code cannot drift |
| Developer commands | `scripts/dev.sh up|down|test|migrate|seed` wrappers; `docker compose run --rm api pytest -q` is the canonical test command |

## 12.8 Database migration strategy

Alembic only; see `04_DATABASE.md` §4.6. One migration per task; reviewed by hand (CHECK constraints, partial indexes, triggers are not auto-generated reliably); `upgrade head` then `downgrade base` tested in CI against a PostGIS service container; **no applied migration is edited**; schema changes need approval; never reset or drop a shared database without explicit approval.

## 12.9 CI pipeline (to build, task B1-A1-02 and B1-A3-19)

| Job | Steps |
|---|---|
| backend | Python 3.11, PostGIS 15 service container, install requirements, `alembic upgrade head`, `pytest -q`, lint |
| frontend | Node LTS, `npm ci`, lint, unit tests, `npm run build` for dashboard and pwa |
| contracts | Regenerate OpenAPI types and fail on a diff (catches contract drift) |
| docs | Mermaid blocks render; markdown links check (proposed) |
| security | secret scan, dependency audit (proposed) |

## 12.10 Documentation standards

- **The repository is the memory.** The seven root documents are updated in every task (`PROJECT_CONTEXT`, `AGENT_RULES`, `IMPLEMENTATION_PLAN`, `STATUS`, `CHANGES`, `DECISIONS_LOG`, `docs/AI_HANDOFF`).
- `CHANGES.md` is append-only and chronological; never delete or rewrite history.
- A feature is "implemented" only when code exists **and** its tests were run; otherwise the status is planned, partial, unverified or blocked.
- Code: type hints, docstrings on services and agents, comments cite the SRS/SDS section (the real v1.1 table numbers — see D-003).
- API: FastAPI OpenAPI is the machine contract; `docs/API_CONTRACT.md` is the human contract; both change together.
- Diagrams in Mermaid in Markdown so they diff in pull requests; exported images for the final report go to `docs/diagrams/`.
- Test reports: `docs/test-reports/<topic>_<date>.md` with command, environment, result.
- Commit messages and PR descriptions never contain secrets or personal data (all data is simulated, NFR-C7).
