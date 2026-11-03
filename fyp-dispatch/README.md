# AI-Assisted Multi-Channel Emergency Dispatch System (Rescue 1122)

Human-in-the-loop emergency dispatch decision support. 3 AI agents (Triage, Coordination,
Resource Allocation) + dispatcher dashboard + driver PWA + live tracking.
Sukkur IBA University, Dept. of Computer Science. Source of truth: `docs/srs-sds/`.

## Quick start
```bash
cp .env.example .env            # then edit secrets
docker compose up -d postgres   # DB first
docker compose up --build api   # API docs: http://localhost:8000/docs
```
Frontend (separate terminals, after creating the Vite apps, see frontend/README.md):
```bash
cd frontend/dashboard && npm install && npm run dev   # http://localhost:5173
cd frontend/pwa       && npm install && npm run dev -- --port 5174
```
Tests: `cd backend && pip install -r requirements.txt && pytest`

## Ownership
| Folder | Owner |
|---|---|
| backend/app (api, agents, services, llm, workers, ws) | Arjun |
| frontend/ | Sumeet |
| db/, backend/migrations, infra/osrm, infra/gazetteer | Khalid |
| docs/ | everyone (chapters per member) |

## Rules
- No direct push to `main`. Branch `feat/<module>-<name>`, open PR, 1 review.
- Never commit `.env`. Schema changes only via Alembic migration PRs.
- Commit style: `feat(triage): add json schema validation`
