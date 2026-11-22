# AMCEDS frontend (web)

npm workspace with three packages (decision D-015):

| Folder | What | Dev address |
|---|---|---|
| `shared/` | Typed API client (types generated from the backend), UI kit, English/Urdu text | — |
| `dashboard/` | Dispatcher + admin dashboard | http://localhost:5173 |
| `pwa/` | Public emergency report page | http://localhost:5174 |

Both ports are in the backend's `CORS_ORIGINS`. All data is SIMULATED.

## First time

Needs Node 22.12+ (tested with Node 24.16, npm 11.13).

```bash
cd frontend
npm install          # exact versions from package-lock.json
```

## Run

Start the backend first (`python3 scripts/run_project.py` from the repository root), then in another terminal:

```bash
cd frontend
npm run dev:dashboard   # http://localhost:5173
npm run dev:pwa         # http://localhost:5174 (third terminal)
```

The API address comes from `VITE_API_URL` (default `http://localhost:8000`).

## Check

```bash
npm test              # unit/component tests (Vitest + React Testing Library)
npm run typecheck     # TypeScript, all three packages
npm run build         # production build of both apps (dist/ is git-ignored)
npm run gen:api:check # are the API types still the same as the running backend's contract?
```

After a backend API change: `npm run gen:api` (backend running) and commit `shared/src/api/schema.ts`.

## Rules

- Use only endpoints that work; a 501 is shown as "not built yet", never as success.
- AI output is always labelled "AI recommendation — dispatcher decides"; every AI value shows its confidence.
- Session tokens live in memory only (never `localStorage`).
- The report page always shows "If life is in danger, also call 1122".
