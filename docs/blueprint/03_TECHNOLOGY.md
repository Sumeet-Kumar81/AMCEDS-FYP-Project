# Part 3 — Technology and library selection

**Rule (project instructions):** the stack below is the approved baseline from SDS v1.1 §4.2. A change needs a DECISIONS_LOG entry and approval. "Proposed" libraries are not yet approved and are listed with the decision that approves them. **Version numbers and library availability were not verified in this blueprint** (no internet in the authoring environment); each is checked when its task starts and written to CHANGES.md.

Cost column: **Free** = open source or free tier with no payment needed for the prototype.

## 3.1 Backend and AI

| Component | Technology | Library / framework | Purpose | Why suitable | Cost | Hardware | Integration notes | Status |
|---|---|---|---|---|---|---|---|---|
| API server | Python 3.11 | FastAPI, Pydantic v2, Uvicorn | REST + WebSocket, validation | Async, typed, auto OpenAPI (feeds the typed frontend client) | Free | low | `/api/v1` prefix (D-006) | Approved (SW-1) |
| ORM / DB access | SQLAlchemy 2 async, asyncpg, GeoAlchemy2 | same | Models, PostGIS types | Project instruction; async matches FastAPI | Free | — | GeoAlchemy2 helpers needed in Alembic `env.py` | Approved |
| Migrations | Alembic | `alembic` (async template) | Versioned schema | Standard with SQLAlchemy | Free | — | Exclude PostGIS internal tables | Approved |
| Auth | JWT + bcrypt | `pyjwt` or `python-jose`, `passlib[bcrypt]` or `bcrypt` | Login, sessions | NFR-C1 salted hashes | Free | — | Session table for idle timeout (D-023) | Approved stack; library choice at B1-A1-14; dependency approval needed |
| WebSocket | FastAPI/Starlette WebSocket | built in | Live updates | No extra service | Free | — | Hub in API process; NOTIFY bridge | Approved |
| Job queue | PostgreSQL | `FOR UPDATE SKIP LOCKED`, `LISTEN/NOTIFY` via asyncpg | Worker hand-off | No Redis needed (D-010) | Free | — | Polling fallback 2 s | Approved (D-010) |
| Orchestration | LangGraph | `langgraph` | Runs agent stages in order with typed state | SDS Table 4.1 | Free | — | Wraps plain functions; **import not verified here** | Approved (SW-3) |
| LLM Gateway | Own Python interface | `httpx` | One interface, many models | SW-3 replaceable | Free | — | Providers: Ollama (local), OpenAI-compatible hosted (e.g. Groq), FakeLLM for tests | Gateway approved; provider **D-008 open** |
| Language model | Open-weight (Llama/Mistral class) via Ollama, or hosted | — | Triage only | SRS SW-3 | Free local / free-tier hosted | Local: 16 GB RAM tight with everything else; GPU optional | Choose by B1-A2-17 evaluation numbers | **D-008 open** |
| Speech-to-text | Whisper via faster-whisper | `faster-whisper` | Voice → text + language | SW-2 | Free | CPU `small` model workable; more RAM for larger | One model per worker; `transcript_unclear` from log-prob | Approved (SW-2); dependency approval needed |
| Geocoding | Pilot gazetteer + Nominatim | stdlib `difflib`, `httpx` | Landmark/address → point | SW-6; gazetteer is faster and works offline | Free | — | Nominatim ≤ 1 request/s; cache | **D-009 open** |
| Routing | OSRM + OpenStreetMap | OSRM container, `httpx` client | Route, distance, ETA; `table` for many vehicles | SW-5 | Free | Needs RAM to prepare the pilot extract (small area) | Straight-line fallback marked approximate | Approved (SW-5) |
| Text similarity | Sentence-transformers or char n-gram TF-IDF | `sentence-transformers` (proposed) | "Meaning" signal for duplicates | Multilingual support | Free | model download, a few hundred MB | Fallback n-gram needs no dependency | **D-007 open** |
| Push | Firebase Cloud Messaging | `firebase-admin` or HTTP v1 | Driver alert backup/primary | SW-10 | Free tier | — | Needs a Firebase project owner (D-013) | **D-013 open** |
| SMS | Simulator | own module | Intake and caller confirmation | SW-11 allows simulator | Free | — | Webhook + secret (D-014) | **D-014 open** |

## 3.2 Frontend and mobile

| Component | Technology | Library | Purpose | Why suitable | Cost | Notes | Status |
|---|---|---|---|---|---|---|---|
| Dispatcher dashboard + admin | React | Vite, TypeScript, React Router, TanStack Query | Screens, data fetching and cache | SDS says React; TS catches contract drift | Free | Typed client generated from `/openapi.json` | React approved; TS/Vite **D-015 open** |
| Public report page | React | same app family | Report without login | Small, mobile-first | Free | MediaRecorder for voice, Geolocation API | Approved (SW-8) |
| Maps (web) | Leaflet + OSM tiles | `leaflet`, `react-leaflet` | Live map, route preview | SW-7 | Free | Tile usage policy and attribution (D-028) | Approved (SW-7) |
| Styling | Tailwind (optional) | — | Fast consistent UI | Styling only | Free | | D-015 |
| Web tests | Jest + React Testing Library (SDS §8.1) or Vitest | — | Component tests | | Free | Vitest is a deviation to record | D-015 |
| Mobile app | React Native (Android) | `react-native`, navigation, background-location, notification and storage libraries | Citizen + driver app | SW-9 / D-002 approved | Free | Expo dev-build vs bare **still open** | Approved (D-002); sub-choice open |
| Mobile maps/navigation | In-app map + OSRM route, with one-tap external navigation fallback | `react-native-maps` or MapLibre RN; TTS library | UC-08 navigation | Works with OSRM, no paid SDK | Free | D-016 | **D-016 open** |

## 3.3 Data, infrastructure, quality

| Component | Technology | Purpose | Notes | Status |
|---|---|---|---|---|
| Database | PostgreSQL 15 + PostGIS (`postgis/postgis:15-3.4`) | All data, spatial queries | Already in `docker-compose.yml` | Approved |
| Containers | Docker, Docker Compose | One-command start | Add `ai-worker`, `osrm`, `nginx`, optional `ollama` | Approved |
| TLS | nginx + local CA (e.g. mkcert) | NFR-C3 | Android must trust the CA (D-024) | **D-024 open** |
| OS | Ubuntu 22.04+ | Server | SRS §5.4 | Approved |
| Backend tests | pytest, pytest-asyncio, httpx | Unit/API/integration | `asyncio_mode = auto` needs `pytest-asyncio` | Approved (SDS §8.1) |
| API manual tests | Postman collection | SDS §8.1 | Optional extra | Approved |
| CI | GitHub Actions | Tests on push | Add PostGIS service container | Exists, unverified |
| Lint/format | `ruff`, `black` or `ruff format`; `eslint`, `prettier` | Style | Proposed | needs D-entry |
| Load testing | `locust` or a small asyncio script | NFR-P6 | Proposed | needs D-entry |

## 3.4 Hardware budget (estimates, not measurements)

Target machine (SRS HW-1): 16 GB RAM, 8 cores, GPU optional. Rough planning figures — **measure in Month 2** and replace:

| Service | Typical memory (estimate) | Note |
|---|---|---|
| PostgreSQL + PostGIS | 0.5–1 GB | small simulated data |
| API | 0.3–0.5 GB | |
| AI worker (without STT/LLM) | 0.3–0.6 GB | |
| faster-whisper `small` (CPU) | 1–2 GB | per loaded model |
| OSRM (pilot-area extract) | 0.5–2 GB | depends on area size |
| Local LLM (7–8B, quantised) via Ollama | 5–8 GB | the largest item |
| Dev tools, browser, Android emulator | 3–5 GB | |

Everything together on 16 GB is tight if the LLM is local. Mitigation: hosted LLM for development, local model only for the final offline demo, or a smaller model — decided by evidence in B1-A2-17 (risk R1).

## 3.5 Alternatives considered (not adopted, with reason)

| Idea | Why not now |
|---|---|
| Redis / Celery queue | New service not in SDS; DB queue is enough for 50 simultaneous reports |
| Microservices per agent | Violates A-001; more operations work for three students |
| Flutter | SDS/project instructions pick React Native (D-002) |
| PWA for driver | Background GPS and push are unreliable on Android (D-002) |
| One LLM prompt for the whole pipeline | Violates "three agents with separate responsibilities"; unsafe to let a model decide dispatch |
| Paid maps/routing SDKs | Budget; OSRM + OSM approved |
