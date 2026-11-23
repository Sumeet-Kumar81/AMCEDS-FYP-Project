# AMCEDS — Code samjhne ki guide (8 hisse)

Ye file batati hai ke **ab tak jo bana hai us ka code kahan hai, kaunsa framework use hua hai, aur code kaise kaam karta hai** — khaas taur par **AI agents** ka code. Har hisse mein:

1. **Files** — kaunsi file kya karti hai,
2. **Asal code** — project ki file se liya gaya tukda (lambi files mein `…` se kuch hissa chhoda gaya hai),
3. **Matlab** — aasaan alfaaz mein.

> Padhne ka mashwara: pehle **Hissa A (naqsha)** aur **Hissa B (frameworks)**, phir **Hissa 3 (AI agents)**, phir baaqi. Har file ke upar ek docstring (`"""…"""` ya `// …`) hai jo khud batati hai ke file kya karti hai — wahan se shuru karein.

---

## Hissa A — Poore system ka naqsha

```
 Shehri (browser)                     Dispatcher (browser)               Driver (abhi /docs se)
 frontend/pwa  :5174                  frontend/dashboard :5173
        │  POST /api/v1/reports              │  GET /incidents, POST /dispatch …     │ /driver/assignments/…
        ▼                                    ▼                                       ▼
 ┌─────────────────────────────── FastAPI (backend/app) :8000 ───────────────────────────────┐
 │ api/routes/*   →  services/*  →  models/* (SQLAlchemy)  →  PostgreSQL + PostGIS            │
 │ (HTTP ka darwaza)  (asal kaam)    (tables)                  (database)                      │
 └────────────────────────────────────────────────────────────────────────────────────────────┘
        │ report save hoti hai, saath "NOTIFY report_pending"
        ▼
 ┌──────────────── AI worker (backend/app/workers/ai_worker.py), alag process ────────────────┐
 │ job uthata hai → Orchestrator (LangGraph) → geocoding → TRIAGE AGENT (Groq LLM)            │
 │                  → TRUST SCORER (rules) → coordination (abhi nahi) → RESOURCE ALLOCATION  │
 │ har qadam ka nateeja database mein save                                                    │
 └────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Sab se ahem usool (safety rules) jo code mein jagah jagah nazar aayenge:**
1. Report **pehle save**, AI baad mein.
2. Koi gaari **dispatcher ki approval ke baghair** nahi jati.
3. High/critical report trust check ki wajah se **kabhi nahi rukti**.
5. Fake report kabhi dispatch nahi hoti.
6. Gaari sirf approval par lock hoti hai; ek gaari ka ek waqt mein ek hi kaam.
7. AI fail ho to report **manual mode** mein, kuch zaya nahi.
9. Har AI nateeja aur faisla **audit log** mein; audit badla nahi ja sakta.

---

## Hissa B — Frameworks aur libraries (kya, kahan, kyun)

### Backend (Python 3.11) — `backend/requirements.txt`
| Library | Version | Kahan | Kyun |
|---|---|---|---|
| **FastAPI** | 0.165 | `app/main.py`, `app/api/routes/*` | Web API banana; har function ek URL (endpoint) ban jata hai; khud `/docs` (Swagger) bana deta hai |
| **Uvicorn** | 0.54 | `docker-compose.yml` (`uvicorn app.main:app`) | FastAPI ko chalane wala server |
| **Pydantic** v2 | 2.14 | `app/schemas/*` | Data ki shakal (schema) aur jaanch: ghalat input → 422 khud |
| **pydantic-settings** | 2.16 | `app/core/config.py` | `.env` se settings padhna |
| **SQLAlchemy** (async) | 2.1 | `app/models/*`, `app/services/*` | Python classes = database tables (ORM) |
| **asyncpg** | 0.32 | SQLAlchemy ke neeche | PostgreSQL se tez async connection; worker ka `LISTEN` |
| **GeoAlchemy2** + **PostGIS** | 0.21 | `models/incident.py`, `fleet.py` | Jagah (lat/lon) store karna, doori naapna |
| **Alembic** | 1.20 | `backend/migrations/versions/*` | Database tables banana/badalna (migrations) |
| **LangGraph** | 1.2.24 | `app/agents/orchestrator.py` | AI qadamon ka graph (state machine) — **agent orchestration** |
| **httpx** | 0.28 | `app/llm/openai_compatible.py`, `ollama.py` | Groq/Ollama ko HTTP request (koi vendor SDK nahi) |
| **bcrypt** | 5.0 | `app/core/security.py` | Password hash |
| **python-jose** | ≥3.3 | `app/core/security.py` | JWT tokens (login) |
| **pytest** + pytest-asyncio | 9.2 / 1.5 | `backend/tests/*` | Backend tests |

**LLM (AI model):** Groq ka hosted model `openai/gpt-oss-120b`, Groq ki **OpenAI-compatible HTTP API** se. LangChain ka agent/tool system **use nahi** hua — sirf LangGraph ka graph, aur model ko hamari apni chhoti "gateway" class se bulaya jata hai.

### Frontend (TypeScript) — `frontend/package.json`
| Library | Version | Kahan | Kyun |
|---|---|---|---|
| **React** | 19.3 | dono apps | Screen (components) banana |
| **TypeScript** | 5.9 | har `.ts/.tsx` | JavaScript + types (ghalti compile par pakdi jaye) |
| **Vite** | 8.3 | `vite.config.ts` | Dev server (`npm run dev`) aur build |
| **React Router** | 7.18 | `dashboard/src/App.tsx` | Pages: `/login`, `/queue`, `/incidents/:id`, `/admin` |
| **TanStack React Query** | 5.107 | `QueuePage`, `IncidentPage`, `DispatchPanel` | Server se data lana, har 5 s refresh, cache |
| **openapi-typescript** | 7.13 | `frontend/scripts/gen-api.mjs` | Backend ke `/openapi.json` se TypeScript types khud banana |
| **Vitest** + Testing Library + jsdom | 5.1 | `*.test.ts(x)` | Frontend tests |
| Styling | — | `*.css` | Saada CSS (Tailwind nahi) |

### Chalane ka tool
`scripts/run_project.py` — sirf Python standard library; Docker Compose commands chalata hai (Hissa 1).

---

## Hissa C — Backend ki "layers" (har feature isi tarah bana hai)

| Layer | Folder | Kaam | Misaal |
|---|---|---|---|
| Route | `app/api/routes/` | HTTP request lena, role check, jawab dena | `reports.py` → `POST /api/v1/reports` |
| Schema | `app/schemas/` | Request/response ki shakal aur jaanch (Pydantic) | `ReportIn`, `IncidentDetailOut` |
| Service | `app/services/` | Asal kaam (business logic), ek transaction | `intake.create_report` |
| Model | `app/models/` | Database table (SQLAlchemy) | `Incident`, `Vehicle`, `Assignment` |
| Migration | `backend/migrations/versions/` | Tables, indexes, triggers banana | `0002_initial_schema.py` |
| Agents / LLM / Worker | `app/agents/`, `app/llm/`, `app/workers/` | AI ka kaam (Hissa 3) | `TriageAgent` |

Ek request ka safar: **route** → (Pydantic **schema** body check karta hai) → **service** → **model** → database → **commit** → jawab.

---

## Hissa 1 — Buniyaad: database, settings, login, roles, launcher

### Files
| File | Kaam |
|---|---|
| `app/main.py` | FastAPI app banana, CORS, saare routers jorna |
| `app/core/config.py` | `.env` se settings (`DATABASE_URL`, `LLM_*`, `JWT_*` …) |
| `app/core/db.py` | Database engine aur session |
| `app/core/security.py` | Password hash (bcrypt), JWT token banana/parhna |
| `app/models/*.py` | 15 tables: users, user_sessions, callers, incidents, incident_groups, vehicles, vehicle_locations, hospitals, recommendations, assignments, audit_logs, settings, duplicate_candidates, confirmation_requests, worker_heartbeats |
| `migrations/versions/0001…0003` | PostGIS on, saari tables + triggers, 35 settings |
| `app/services/settings.py` | 35 settings, un ki had (range), har report ke saath "snapshot" |
| `app/services/audit.py` | Audit log ki row likhna |
| `app/services/auth.py` | Login, 5 ghalat par lock, session, idle logout |
| `app/api/deps.py` | "Kaun login hai" aur role check (`DISPATCHER`, `DRIVER`, `ADMIN`) |
| `app/api/errors.py` | Har error ki ek shakal: `{code, message, details}`; na bane endpoint → 501 |
| `app/seed.py` | SIMULATED sample data (9 users, 6 gaariyan, 2 hospitals) |
| `scripts/run_project.py` | Ek command se sab chalana/rokna/test |

### Asal code: password aur token — `app/core/security.py`
```python
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

def verify_password(password: str, password_hash: str) -> bool:
    …
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
```
**Matlab:** database mein asli password kabhi nahi jata, sirf us ka bcrypt "hash". Login par naya hash mila kar dekhte hain. Token **HS256** JWT hai (15 min), saath refresh token (12 h).

### Asal code: role check — `app/api/deps.py`
```python
DISPATCHER = require_roles(UserRole.DISPATCHER)
DRIVER = require_roles(UserRole.DRIVER)
ADMIN = require_roles(UserRole.ADMIN)

async def require_driver_owns_assignment(assignment_id: int, auth = Depends(DRIVER), db = Depends(get_db)):
    row = (await db.execute(select(Assignment.assignment_id, Vehicle.driver_id)
           .join(Vehicle, Vehicle.vehicle_id == Assignment.vehicle_id)
           .where(Assignment.assignment_id == assignment_id))).first()
    if row is None:
        raise ApiError(404, "No such assignment.", code="not_found")
    if row.driver_id != auth.user.user_id:
        raise ApiError(403, "This assignment belongs to another vehicle.", code="forbidden")
    return auth
```
**Matlab:** har private route ke saath `Depends(DISPATCHER)` jaisa "pehra" laga hai. FastAPI route chalane se pehle ye function chalata hai: login nahi → 401, ghalat role → 403. Driver sirf **apni gaari** ki assignment chhoo sakta hai (TC-48).

### Asal code: database khud reference number banata hai — `app/models/incident.py`
```python
REFERENCE_NO_SQL = (
    "'INC-' || CASE WHEN incident_id < 1000000 THEN lpad(incident_id::text, 6, '0') ELSE incident_id::text END"
)
…
reference_no: Mapped[str] = mapped_column(Text, Computed(REFERENCE_NO_SQL, persisted=True), unique=True)
```
**Matlab:** `INC-000012` PostgreSQL **save hui row** se banata hai — is liye reference number sirf tab milta hai jab report sach mein save ho (safety rule 1).

### Asal code: database ki hifazat (triggers) — `migrations/versions/0002_initial_schema.py`
```python
op.create_index('uq_assignments_open_vehicle', 'assignments', ['vehicle_id'], unique=True,
                postgresql_where=sa.text("status IN ('accepted', 'approved')"))
…
CREATE TRIGGER audit_logs_no_modify BEFORE UPDATE OR DELETE ON audit_logs …
CREATE TRIGGER incidents_keep_original BEFORE UPDATE OF original_text, audio_ref ON incidents …
```
**Matlab:**
- Ek gaari ki **ek hi khuli assignment** — database khud rokta hai (safety rule 6 ki aakhri deewar).
- Audit log ko **update/delete nahi** kar sakte; asli report ka text **ek dafa** likha jata hai (safety rule 9).

---

## Hissa 2 — Report bhejna (save pehle, AI baad mein)

### Files
| File | Kaam |
|---|---|
| `app/schemas/report.py` | `ReportIn`: text 1–2000; **jagah, naam aur phone zaroori** (D-036); phone `^03[0-9]{9}$` (11 hindse, `03` se shuru; space/dash pehle hata diye jate hain); lat/lon jora; sirf web/app |
| `app/api/routes/reports.py` | `POST /api/v1/reports` — 201 / 200 (dobara) / 503 |
| `app/services/intake.py` | Caller dhoondna, incident insert, audit, `NOTIFY` |

### Asal code: route — `app/api/routes/reports.py`
```python
async def submit_report(body: ReportIn, response: Response, db: AsyncSession = Depends(get_db)) -> ReportAcceptedOut:
    try:
        incident, created = await intake.create_report(db, body)
        await db.commit()
    except IntegrityError:
        await _safe_rollback(db)
        if body.client_request_id:  # the same report arrived twice at the same moment
            existing = await intake.find_by_client_request_id(db, body.client_request_id)
            if existing is not None:
                response.status_code = 200
                return _accepted(existing)
        raise ApiError(503, NOT_SAVED, code="service_unavailable") from None
    except (SQLAlchemyError, OSError):
        await _safe_rollback(db)
        raise ApiError(503, NOT_SAVED, code="service_unavailable") from None
    if not created:
        response.status_code = 200
    return _accepted(incident)
```
**Matlab:**
- `body: ReportIn` — FastAPI + Pydantic pehle body jaanchte hain; ghalat ho to **422** aur ye function chalta hi nahi. D-036 ke baad jagah (`address_text`), naam (`reporter_name`) aur phone (`reporter_phone`, 11 hindse `03` se shuru) ke baghair bhi 422.
- `commit()` ke **baad** hi jawab. Database band ho to **503** aur koi reference number nahi.
- Wahi `client_request_id` dobara aaye to **200** aur purana reference — report do dafa save nahi hoti (TC-04).

### Asal code: service — `app/services/intake.py` (chhota kiya hua)
```python
async def create_report(db, body):
    if body.client_request_id:
        existing = await find_by_client_request_id(db, body.client_request_id)
        if existing is not None:
            return existing, False
    caller = await _caller(db, body.phone_digits, body.device_id, now)
    if has_gps:            source = LocationSource.GPS
    elif body.address_text: source = LocationSource.TEXT
    else:                  source = LocationSource.UNKNOWN
    incident = Incident(…, status="new", pipeline_state="pending",
                        review_reasons=["location_unknown"] if source is LocationSource.UNKNOWN else [],
                        settings_snapshot=await get_snapshot(db))
    db.add(incident); await db.flush()
    await record(db, AuditAction.REPORT_RECEIVED, incident_id=incident.incident_id, details={…})
    await db.execute(text("SELECT pg_notify(:channel, :payload)"), {"channel": JOB_NOTIFY_CHANNEL, …})
    return incident, True
```
**Matlab:**
- `pipeline_state = "pending"` → ye AI ke liye **job** hai (alag queue system ki zaroorat nahi — database hi queue hai).
- `settings_snapshot` → us waqt ki settings report ke saath save; baad mein settings badlein to purani reports par asar nahi.
- `pg_notify` → PostgreSQL commit ke waqt AI worker ko "jaago, nayi report aayi" bhejta hai.
- **Is file mein koi AI nahi** — AI alag process mein (Hissa 3).

---

## Hissa 3 — AI agents (sab se ahem) 🤖

### "Agent" yahan kis cheez ko kaha gaya hai?
SDS ke mutabiq **teen agents** hain; is waqt do bane hain, aur ek rule-based scorer:

| Naam | File | LLM use? | Kaam | Haal |
|---|---|---|---|---|
| **Triage Agent** | `app/agents/triage.py` + `prompts/triage_v1.md` | ✅ Groq | Report padh kar type, severity, zakhmi, zaban, jagah ke alfaaz, confidence | ✅ |
| **Trust Scorer** (agent **nahi**, rules) | `app/agents/trust.py` | ❌ | 50 se shuru, har signal ke points aur wajah, tier | ✅ |
| Urgency policy | `app/agents/policy.py` | ❌ | Trust × severity → agla qadam | ✅ |
| **Resource Allocation Agent** | `app/agents/resource.py` | ❌ (rules + doori) | Kitni/kaunsi gaariyan, qareeb pehle, ETA | ✅ |
| **Coordination Agent** | `app/agents/coordination.py` | — | Duplicate reports milana | ❌ abhi sirf khaali file |
| **Orchestrator** | `app/agents/orchestrator.py` | — | **LangGraph** se in sab ko tarteeb mein chalana | ✅ |
| LLM Gateway | `app/llm/gateway.py`, `openai_compatible.py`, `ollama.py`, `fake.py` | — | Model badalna sirf `.env` se | ✅ |
| AI worker | `app/workers/ai_worker.py` | — | Database se job uthana, orchestrator chalana | ✅ |
| Pipeline store | `app/services/pipeline_store.py` | — | Har qadam ka nateeja database mein likhna | ✅ |
| AI schemas | `app/schemas/ai.py` | — | `TriageResult`, `TrustAssessment`, `AllocationResult` | ✅ |

> Ahem baat: **AI sirf mashwara deta hai.** Koi bhi agent status "dispatched" nahi kar sakta, gaari lock nahi kar sakta. Model jo bhi likhe, sirf 12 tay shuda keys li jati hain.

### 3.1 LLM Gateway — model ko kaise bulaya jata hai
`app/llm/gateway.py`:
```python
class LLMClient(ABC):
    """The replaceable gateway. …"""
    @abstractmethod
    async def complete_json(self, system: str, user: str) -> LLMResponse:
        """Ask the model, temperature 0, and return its JSON object. Raises ``LLMError``/``LLMTimeout``."""

def get_llm_client(settings=None) -> LLMClient:
    provider = (settings.llm_provider or "").strip().lower()
    if provider == "groq":
        return OpenAICompatibleClient(base_url=… or GROQ_BASE_URL, api_key=settings.llm_api_key,
                                      model=settings.llm_model, timeout_s=timeout, provider="groq")
    if provider == "ollama":
        return OllamaClient(base_url=settings.ollama_url, model=settings.llm_model, timeout_s=timeout)
    raise ValueError(f"LLM_PROVIDER '{settings.llm_provider}' is not supported …")
```
`app/llm/openai_compatible.py`:
```python
async def complete_json(self, system: str, user: str) -> LLMResponse:
    if not self._key:
        raise LLMError("LLM_API_KEY is not set")
    body = {
        "model": self.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    …
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            reply = await client.post(self._url, json=body, headers={"Authorization": f"Bearer {self._key}"})
    except httpx.TimeoutException:
        raise LLMTimeout() from None
    …
    if reply.status_code >= 400:
        transient = reply.status_code == 429 or reply.status_code >= 500
        raise LLMError(f"language model returned HTTP {reply.status_code}", transient=transient)
    …
    return LLMResponse(data=extract_json(content), model=str(model), latency_ms=latency)
```
**Matlab:**
- **Ek hi darwaza** (`complete_json`): baaqi code ko pata nahi ke andar Groq hai ya Ollama. Model badalna = `.env` mein `LLM_PROVIDER`/`LLM_MODEL` badalna.
- `temperature: 0` → har dafa ek jaisa, kam "creative" jawab.
- `response_format: json_object` → model se **sirf JSON** maanga jata hai.
- Request seedhi **httpx** se Groq ke `/chat/completions` par (OpenAI jaisi API). Koi SDK nahi.
- Errors do qisam: **transient** (timeout, 429, 5xx → dobara koshish) aur **permanent** (ghalat key, 404 model → manual mode).
- API key sirf header mein; logs/errors mein kabhi nahi.
- `fake.py` → tests ke liye nakli model (internet ke baghair, hamesha tay jawab).

### 3.2 Triage Agent — report kaise padhi jati hai
**Prompt** `app/agents/prompts/triage_v1.md` (system message) model ko batata hai:
```
Return ONLY one JSON object, with exactly these keys:
- "language": one of "English", "Urdu", "Sindhi", "Roman Urdu", "Mixed", or null …
- "incident_type": one of "accident", "fire", "medical", "other", or null if the report does not say
- "severity": one of "low", "medium", "high", "critical", or null …
- "victims_estimate": … - "location_words": … - "has_real_details": … - "vague_or_joking": …
- "overall_confidence": number from 0 to 1 …
Rules:
1. Use null when the report does not say something. Never guess.
2. Never invent a location. …
```
Saath 4 SIMULATED misalein (English, Urdu script, Roman Urdu, vague) — "few-shot".

**Code** `app/agents/triage.py`:
```python
class TriageAgent:
    def __init__(self, llm: LLMClient, prompt_version: str = PROMPT_VERSION) -> None:
        self.llm = llm
        self.system = load_prompt(prompt_version)

    @staticmethod
    def user_message(inp: TriageInput, hint: str | None) -> str:
        lines = [f"Report: {inp.text!r}"]
        …
        if hint:
            lines.append(f"Writing system suggests the language: {hint}")
        return "\n".join(lines)

    async def run(self, inp: TriageInput, *, transcript_unclear: bool = False) -> TriageResult:
        hint = inp.language_hint or script_language(inp.text)
        base = self.user_message(inp, hint)
        error: str | None = None
        for _attempt in range(2):
            message = base if error is None else (
                f"{base}\n\nYour previous answer was rejected: {error}\nReturn the corrected JSON object only.")
            try:
                reply = await self.llm.complete_json(self.system, message)
            except LLMError as exc:
                if exc.transient:
                    raise
                error = str(exc)
                continue
            try:
                return self._result(reply.data, reply.model, reply.latency_ms, inp, hint, transcript_unclear)
            except (ValidationError, ValueError, TypeError) as exc:
                error = _short(exc)
        raise TriageFailed(f"invalid model output twice: {error}")
```
```python
def _clean(data):
    missing = [k for k in MODEL_KEYS if k not in data]
    if missing:
        raise ValueError(f"missing keys: {', '.join(missing)}")
    out = {k: data[k] for k in MODEL_KEYS}        # sirf 12 keys — baaqi sab phenk di jati hain
    …  # "unknown", "null", "" → None; "Fire" → "fire"; "ur" → "Urdu"
```
**Matlab (qadam ba qadam):**
1. `script_language()` — text ke huroof dekh kar ishara: Arabic script → Urdu (ya Sindhi agar Sindhi ke khaas huroof hon), mila jula → Mixed. Latin (English/Roman Urdu) ka faisla model karta hai.
2. Report `!r` se **quote** ki jati hai — report ka text instructions mein mil nahi sakta ("ignore the rules" jaisi chaal kaam nahi karti).
3. Model ka JSON `_clean` se guzarta hai: **sirf 12 keys**. Model "status: dispatched" likhe to bhi phenk diya jata hai.
4. Phir **Pydantic** `TriageResult` jaanchta hai (confidence 0–1, type tay list mein…).
5. Ghalat jawab → **ek dafa** dobara, model ko ghalti bata kar. Phir bhi ghalat → `TriageFailed` → report manual mode.
6. `missing_fields` hamara apna rule: type ya jagah na ho to `missing_info` (TC-07).
7. 60% se kam confidence ka faisla save karte waqt hota hai (`low_confidence`) — report **fake nahi** banti.

### 3.3 Trust Scorer — rules (LLM nahi)
`app/agents/trust.py`:
```python
def signals_for(i: TrustInputs, s: TrustSettings = DEFAULT_SETTINGS) -> list[TrustSignal]:
    out = []
    def add(code, points, detail): out.append(TrustSignal(code=code, points=points, detail=detail))
    if i.real_count > 0:
        add("real_history", s.real_history, f"{i.real_count} earlier report(s) from this caller confirmed real")
    if i.fake_count > 0:
        add("fake_history", max(s.fake_floor, s.fake_each * i.fake_count), …)
    …
    if i.has_real_details is None and i.vague_or_joking is None:
        add("ai_unavailable", 0, "Triage AI unavailable: message details not scored (D-035)")
    else:
        if i.has_real_details:
            add("real_details", s.real_details, "the message names a place, an event or people hurt")
        if i.vague_or_joking:
            add("vague", s.vague, "the message is vague or joking")
    …

class TrustScorer:
    def assess(self, inputs, severity, settings=None) -> TrustAssessment:
        s = TrustSettings.from_settings(settings or {})
        signals = signals_for(inputs, s)
        score = max(0, min(100, s.start + sum(x.points for x in signals)))
        tier = tier_for(score, s)
        return TrustAssessment(score=score, tier=tier, signals=signals, action=decide_action(tier, severity))
```
**Matlab:** 50 se shuru; har signal ke points (+10 asli details, −15 vague, purani fake reports…) aur **har point ki wajah**. Score 0–100 → tier (high/medium/low). Saare numbers settings se aate hain (admin baad mein badal sake). AI fail ho to AI wale signals chhod diye jate hain aur "ai_unavailable" likha jata hai.

### 3.4 Urgency policy — `app/agents/policy.py`
```python
def is_urgent(severity) -> bool:
    """High, critical or unknown: never held back."""
    return severity is None or Severity(severity) in URGENT_SEVERITIES

def decide_action(tier, severity) -> TrustAction:
    if tier is TrustTier.HIGH:   return TrustAction.CONTINUE
    if tier is TrustTier.MEDIUM: return TrustAction.CONTINUE_AND_CONFIRM
    return TrustAction.URGENT_WITH_WARNING if is_urgent(severity) else TrustAction.REVIEW_QUEUE

def allocate_now(action) -> bool:
    return TrustAction(action) is not TrustAction.REVIEW_QUEUE
```
**Matlab:** kam trust + **high/critical/maloom nahi** → "urgent with warning" — **report rukti nahi** (safety rule 3), gaariyon ka mashwara foran. Sirf kam trust + low/medium → review queue, mashwara baad mein.

### 3.5 Resource Allocation Agent — `app/agents/resource.py`
```python
def vehicles_needed(incident_type, severity, victims, patients_per_ambulance) -> Needed:
    if incident_type is None or IncidentType(incident_type) is IncidentType.OTHER:
        return Needed({}, check_victims=False, dispatcher_chooses=True)
    unknown = victims is None
    ambulances = 1 if unknown else max(1, math.ceil(victims / patients_per_ambulance))
    if kind is IncidentType.ACCIDENT:
        counts = {VehicleType.AMBULANCE: ambulances}
        if severity is not None and Severity(severity) is Severity.CRITICAL:
            counts[VehicleType.BACKUP] = 1
    elif kind is IncidentType.FIRE:
        counts = {VehicleType.FIRE_TRUCK: 1, VehicleType.AMBULANCE: ambulances, VehicleType.BACKUP: 1}
    else:  # medical
        counts = {VehicleType.AMBULANCE: ambulances}
    …

class StraightLineEta:
    async def eta(self, from_lat, from_lon, to_lat, to_lon) -> Eta:
        meters = straight_line_m(from_lat, from_lon, to_lat, to_lon)      # haversine
        return Eta(seconds=round(meters / self.speed_ms), meters=round(meters), approximate=True)
```
**Matlab:**
- Accident: zakhmi ÷ ek ambulance mein kitne mareez (setting) = ambulances; critical par +1 backup. Aag: fire truck + ambulances + backup.
- Type maloom nahi / "other" → saari gaariyan qareeb pehle, **dispatcher chunega**.
- ETA abhi **seedhi lakeer** (haversine) aur fix speed se — is liye hamesha **"approximate"** (asal road route OSRM baad mein).
- Zaroori gaariyan + 2 spare, qareeb pehle; kam hon to `shortage`.
- Ye sirf **list** banata hai — kuch save/lock nahi karta.

### 3.6 Orchestrator — **LangGraph** se sab ko jorna — `app/agents/orchestrator.py`
```python
from langgraph.graph import END, START, StateGraph

class _State(TypedDict, total=False):
    job: PipelineJob
    geocode: GeocodeResult
    triage: TriageResult | None
    trust: TrustAssessment
    failed: PipelineStage | None

def _build(self):
    g = StateGraph(_State)
    g.add_node("speech_to_text", self._speech_to_text)
    g.add_node("geocoding", self._geocoding)
    g.add_node("triage", self._triage)
    g.add_node("trust", self._trust)
    g.add_node("coordination", self._coordination)
    g.add_node("allocation", self._allocation)
    g.add_node("finish", self._finish)
    g.add_conditional_edges(START, lambda s: "speech_to_text" if self._needs_stt(s["job"]) else "geocoding",
                            ["speech_to_text", "geocoding"])
    g.add_edge("speech_to_text", "geocoding")
    g.add_edge("geocoding", "triage")
    g.add_edge("triage", "trust")
    g.add_conditional_edges("trust", lambda s: END if s.get("failed") else "coordination", ["coordination", END])
    g.add_edge("coordination", "allocation")
    g.add_edge("allocation", "finish")
    g.add_edge("finish", END)
    return g.compile()
```
Graph ki shakal:
```
START ─(awaaz, text nahi)─► speech_to_text ─┐
  └──(text)───────────────────────────────► geocoding ─► triage ─► trust ─┬─(fail)─► END (manual mode)
                                                                          └─► coordination ─► allocation ─► finish ─► END
```
Triage node (retry ke saath):
```python
async def _triage(self, state, config):
    …
    attempt = 0
    while True:
        try:
            result = await self.triage.run(inp)
            break
        except TriageFailed as exc:
            return {**await self._fail(out, job, PipelineStage.TRIAGE, str(exc)), "triage": None}
        except LLMError as exc:
            if not exc.transient or attempt >= self.retries:
                return {**await self._fail(out, job, PipelineStage.TRIAGE, f"language model unavailable: {exc}"),
                        "triage": None}
            delay = self.backoff_s[min(attempt, len(self.backoff_s) - 1)] if self.backoff_s else 0
            attempt += 1
            await asyncio.sleep(delay)
    await self.store.save_triage(job.incident_id, result)
    …
```
**Matlab:**
- **LangGraph `StateGraph`** = qadamon (nodes) ka naqsha; ek "state" dictionary (`job`, `geocode`, `triage`, `trust`, `failed`) ek node se doosre tak jati hai.
- `add_conditional_edges` = faisle wale raaste: awaaz ho to pehle speech-to-text; trust ke baad agar triage fail tha to seedha END.
- **Har node apna nateeja foran database mein save** karta hai (`store.save_…`) — baad ka qadam fail ho to pehle ka nateeja nahi mitta.
- Timeout/429 → 2 dafa dobara (0.5 s, 1.5 s ke wqfe se). Phir bhi nahi → `mark_stage_failed` → report `needs_check` + `ai_failed`.
- AI fail ho tab bhi **trust chalta hai** (D-035).
- Jo qadam bane nahi (speech-to-text, geocoding by name, coordination) wo **khule aam "skipped"** likhe jate hain, nakli nateeja nahi.
- `allocation` node: review-queue wali report ko mashwara nahi (`allocate_now`), warna available gaariyan la kar agent chalata hai.

### 3.7 AI worker — `app/workers/ai_worker.py`
```python
async def _slot(self, n: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            job = await self.store.claim_next(JOB_TYPES)
        except Exception:
            logger.exception("slot %s: cannot claim a job (database?); retrying in %.1fs", n, self.poll_s)
            await self._sleep(stop, self.poll_s); continue
        if job is None:
            self.wake.clear()
            await self._sleep(stop, self.poll_s)       # NOTIFY aaye to foran jaagta hai, warna 2 s baad
            continue
        …
            outcome = await self.orchestrator.run(job)
```
Job uthane wali SQL — `app/services/pipeline_store.py`:
```sql
WITH next AS (
    SELECT incident_id, pipeline_state AS job_type FROM incidents
    WHERE pipeline_state = ANY(:types)
    ORDER BY {severity rank}, received_at, incident_id
    FOR UPDATE SKIP LOCKED LIMIT 1
)
UPDATE incidents i
SET pipeline_state = 'processing', pipeline_attempts = i.pipeline_attempts + 1, pipeline_updated_at = now()
FROM next WHERE i.incident_id = next.incident_id
RETURNING …
```
**Matlab:**
- Worker **alag process** hai (Docker service `ai-worker`), API ke saath nahi.
- **2 slots** = do reports ek saath.
- `FOR UPDATE SKIP LOCKED` = do slots/workers kabhi **ek hi report** nahi uthate. Critical pehle.
- `LISTEN report_pending` se foran jaagta hai; NOTIFY gum ho to bhi har 2 s check — report kabhi nahi chhoot-ti.
- Har 10 s **heartbeat** (`worker_heartbeats`), har 60 s phansi hui jobs wapas (`requeue_stale_jobs`); 3 koshishon ke baad manual mode.
- Ctrl+C/SIGTERM par chalta hua kaam poora kar ke band.

### 3.8 Tests (AI)
`backend/tests/unit/agents/`: `test_llm_gateway.py`, `test_triage.py`, `test_trust.py`, `test_policy.py`, `test_resource.py`, `test_orchestrator.py`, `test_worker_loop.py`, `test_ai_schemas.py`, `fakes.py` (nakli store); `backend/tests/integration/test_pipeline_end_to_end.py` (asli database ke saath, nakli model).

---

## Hissa 4 — Dispatcher ke liye data: incident queue aur detail API

### Files
| File | Kaam |
|---|---|
| `app/services/incidents.py` | Queue ki tarteeb, filters, detail (sirf padhna) |
| `app/api/routes/incidents.py` | `GET /api/v1/incidents`, `GET /api/v1/incidents/{id}` |
| `app/schemas/incident.py` | `IncidentSummaryOut`, `IncidentDetailOut`, `RecommendationOut` (+`plate_number`) |

### Asal code — tarteeb
```python
SEVERITY_RANK = case(
    (Incident.severity == Severity.CRITICAL.value, 0),
    (Incident.severity == Severity.HIGH.value, 1),
    (Incident.severity.is_(None), 2),
    (Incident.severity == Severity.MEDIUM.value, 3),
    (Incident.severity == Severity.LOW.value, 4),
    else_=5,
)
…
return query.order_by(SEVERITY_RANK, Incident.received_at, Incident.incident_id)
```
**Matlab:** critical → high → **maloom nahi** (ho sakta hai critical ho) → medium → low; ek severity mein jo **pehle aayi** wo upar. Detail mein sirf **maujooda round** ke mashware, gaari ke **plate** ke saath. Ye API kuch likhti nahi.

---

## Hissa 5 — Gaari bhejna (dispatch approval) aur gaariyon ki list

### Files
| File | Kaam |
|---|---|
| `app/services/dispatch.py` | `approve()` (lock, check, assignment, audit), `next_best()`, `list_vehicles()` |
| `app/api/routes/dispatch.py` | `POST /api/v1/incidents/{id}/dispatch` |
| `app/api/routes/fleet.py` | `GET /api/v1/vehicles`, `GET /api/v1/hospitals` |
| `app/schemas/dispatch.py` | `DispatchIn`, `VehicleOut` |
| `tests/integration/test_dispatch_concurrency.py` | Do dispatcher ek gaari — 50 rounds |

### Asal code — `app/services/dispatch.py` (chhota kiya hua)
```python
async def approve(db, incident_id, body, dispatcher):
    incident = await db.scalar(select(Incident).where(Incident.incident_id == incident_id).with_for_update())
    if incident is None: raise DispatchError(404, "not_found", "No such incident.")
    if incident.status in NOT_DISPATCHABLE:            # fake, closed
        raise DispatchError(409, "incident_not_dispatchable", …)
    wanted = sorted(body.vehicle_ids)
    vehicles = list((await db.scalars(
        select(Vehicle).where(Vehicle.vehicle_id.in_(wanted)).order_by(Vehicle.vehicle_id).with_for_update())).all())
    …
    fits = await _fitness(db, vehicles)                 # locked / not available / no driver / driver off duty
    if locked:  raise DispatchError(409, "vehicle_locked", …, {"vehicle_ids": locked, "next_best": …})
    if unfit:   raise DispatchError(409, "vehicle_unavailable", …, {"vehicles": unfit, "next_best": …})
    assignments = [Assignment(incident_id=incident_id, vehicle_id=v.vehicle_id, approved_by=dispatcher.user_id,
                              hospital_id=body.hospital_id, status="approved", approved_at=now) for v in vehicles]
    db.add_all(assignments)
    try:
        await db.flush()   # the partial unique index decides a same-moment race
    except IntegrityError as exc:
        …  raise DispatchError(409, "vehicle_locked", …)
    for v in vehicles: v.status = "assigned"
    if incident.status in BECOMES_DISPATCHED: incident.status = "dispatched"
    await record(db, AuditAction.DISPATCH_APPROVED, user_id=dispatcher.user_id, incident_id=incident_id, details={
        "recommended": recommended, "selected": wanted, "same_as_ai": …, "override_reason": body.override_reason,
        "manual_mode": not recommended, "signal_lost": signal_lost, …})
```
**Matlab:**
- **Sirf yahi jagah** hai jahan gaari bheji jati hai — aur sirf **logged-in dispatcher** (safety rule 2).
- `with_for_update()` = database row lock: do dispatcher ek saath ek gaari chunein to doosra **intezar** karta hai, phir use "busy" milti hai. Gaariyan **id ki tarteeb** mein lock → deadlock nahi.
- Fake/closed → 409 (safety rule 5). Low trust **rukawat nahi** (safety rule 3).
- Ya saari gaariyan jati hain ya koi nahi (ek transaction).
- Audit mein **AI ne kya kaha vs dispatcher ne kya chuna**.
- Database ka `uq_assignments_open_vehicle` index aakhri hifazat.

---

## Hissa 6 — Driver ka safar (assignment lifecycle)

### Files
| File | Kaam |
|---|---|
| `app/services/assignments.py` | accept, decline, trip steps, cancel, hospital change, driver ka "current" |
| `app/api/routes/driver.py` | `/driver/assignments/current`, `/accept`, `/decline`, `/status` |
| `app/api/routes/dispatch.py` | `/assignments/{id}/cancel`, `/assignments/{id}/hospital` |
| `app/schemas/assignment.py` | Contract C-7: kaunsa qadam kis ke baad (`ASSIGNMENT_TRANSITIONS`, `TRIP_TRANSITIONS`), `DeclineReason` |

### Asal code — tarteeb ka rule (C-7) `app/schemas/assignment.py`
```python
ASSIGNMENT_TRANSITIONS = {
    AssignmentStatus.APPROVED: frozenset({ACCEPTED, DECLINED, TIMED_OUT, CANCELLED}),
    AssignmentStatus.ACCEPTED: frozenset({COMPLETED, CANCELLED}),
    …  # declined, timed_out, completed, cancelled → aage kuch nahi
}
TRIP_TRANSITIONS = {
    (VehicleStatus.EN_ROUTE, TripStatus.ON_SCENE): VehicleStatus.ON_SCENE,
    (VehicleStatus.ON_SCENE, TripStatus.PICKED_UP): VehicleStatus.TRANSPORTING,
    (VehicleStatus.TRANSPORTING, TripStatus.AT_HOSPITAL): VehicleStatus.AT_HOSPITAL,
    (VehicleStatus.AT_HOSPITAL, TripStatus.AVAILABLE): VehicleStatus.AVAILABLE,
    (VehicleStatus.ON_SCENE, TripStatus.AVAILABLE): VehicleStatus.AVAILABLE,  # no patient carried
}
```
### Asal code — report ka anjaam `app/services/assignments.py`
```python
async def _settle_incident(db, incident, reason_if_none_finished):
    …
    if any(counts.get(s, 0) for s in OPEN) or incident.status not in ACTIVE_INCIDENT:
        return None                                     # koi gaari abhi chal rahi hai
    if counts.get(AssignmentStatus.COMPLETED.value, 0):
        incident.status = IncidentStatus.CLOSED.value   # kam az kam ek safar poora
    else:
        incident.status = IncidentStatus.NEEDS_CHECK.value
        incident.review_reasons = sorted(set(incident.review_reasons or []) | {reason_if_none_finished})
```
**Matlab:** har qadam C-7 ki "table" se check hota hai — ghalat tarteeb (accept se pehle "picked up") → 409 aur **kuch nahi badalta**. Har qadam ka waqt save, audit, gaari free hone par `vehicle.unlocked`. Aakhri safar khatam → report **closed**; sab gaariyan decline/cancel → report **dispatcher ke paas wapas** (urgent report gum nahi hoti).

---

## Hissa 7 — Shehri ka report page (frontend `pwa`)

### Files
| File | Kaam |
|---|---|
| `frontend/pwa/src/App.tsx` | Page ka dhaancha: 1122 notice, language toggle, service banner |
| `pwa/src/report/ReportPage.tsx` | Form, bhejna, retry, errors |
| `pwa/src/report/validation.ts` | Form ke rules (backend jaise), body banana, submission id |
| `pwa/src/report/useGeolocation.ts` | Browser GPS |
| `pwa/src/report/LocationField.tsx`, `SentScreen.tsx`, `FieldMessage.tsx` | GPS/jagah hissa, kamyabi screen, field error |
| `frontend/shared/src/api/client.ts` | Har API call ka client (token, refresh, errors, timeout) |
| `shared/src/api/endpoints.ts` | Typed calls: `submitReport`, `login`, `listIncidents`, `dispatchIncident` … |
| `shared/src/api/schema.ts` | Backend se **khud bani** types (`npm run gen:api`) |
| `shared/src/ui/*` | Badges (severity, trust, confidence), 1122 notice, loading/error |
| `shared/src/i18n/*` | English/Urdu alfaaz, Urdu par right-to-left |

### Asal code — ek dafa bhejna, dobara mehfooz `ReportPage.tsx`
```tsx
async function onSubmit(event: FormEvent) {
  event.preventDefault();
  if (inFlight.current) return; // never two requests for one press (double tap)
  const found = validate(draft);
  …
  if (!pending.current || !sameDraft(pending.current.draft, draft)) {
    pending.current = { id: newRequestId(), draft };
  }
  …
  try {
    const result = await submitReport(client, toReportIn(draft, pending.current.id));
    pending.current = null;
    setSent(result);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) setErrors(serverFieldErrors(error.validationIssues));
    setProblem(problemFor(error));
  }
}
```
**Matlab:**
- `useState` / `useRef` = React ki "yaadasht". `inFlight` double-click rokta hai.
- Har report ka ek **`client_request_id`** (UUID). Network gaya aur dobara bheja → **wahi id** → server use dobara save nahi karta. Report badal di → nayi id.
- Kamyabi screen **sirf** server ke 201/200 par.
- `ApiError` ke `status` se sahi message: 503 → "NOT saved, call 1122", network → "not sent".

### Asal code — API client `shared/src/api/client.ts` (khayal)
- Har call par token (`Authorization: Bearer …`) — report par **nahi**.
- 401 → ek dafa refresh token se naya token, phir dobara; fail → session khatam.
- Har error ek shakal: `ApiError {status, code, message, details}`.
- Token sirf **memory** mein (localStorage nahi).

---

## Hissa 8 — Dispatcher dashboard (frontend `dashboard`)

### Files
| File | Kaam |
|---|---|
| `dashboard/src/App.tsx` | Router aur React Query provider; pages |
| `dashboard/src/auth/AuthProvider.tsx` | Login/logout, driver ko rokna, session khatam pehchanna |
| `dashboard/src/auth/guards.tsx` | Bina login → `/login`; ghalat role → "Not allowed" |
| `dashboard/src/auth/useIdleTimer.ts` | 28 min warning, 30 min logout, 5 min keep-alive |
| `dashboard/src/pages/LoginPage.tsx` | Login form aur messages |
| `dashboard/src/layout/AppLayout.tsx` | Upar ki pati, menu, sign out, idle warning |
| `dashboard/src/incidents/QueuePage.tsx` | Queue, har 5 s refresh, nayi critical highlight |
| `dashboard/src/incidents/IncidentPage.tsx` | Review screen: report, AI + confidence, trust, reasons |
| `dashboard/src/incidents/labels.ts` | Codes → alfaaz |
| `dashboard/src/dispatch/DispatchPanel.tsx` | Gaariyan chunna, Approve → Confirm, 409 → next best |
| `dashboard/src/dispatch/selection.ts` | Kaunsi gaariyan pehle se tick hon |
| `dashboard/src/dispatch/TripList.tsx` | Har gaari ka safar, Cancel, hospital badalna |

### Asal code — pages aur hifazat `App.tsx`
```tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
    <Route index element={<HomeRedirect />} />
    <Route path="queue" element={<RequireRole roles={["dispatcher"]}><QueuePage /></RequireRole>} />
    <Route path="incidents/:incidentId" element={<RequireRole roles={["dispatcher"]}><IncidentPage /></RequireRole>} />
    <Route path="admin" element={<RequireRole roles={["admin"]}><AdminPage /></RequireRole>} />
  </Route>
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes>
```
**Matlab:** React Router har URL ke liye page chunta hai; `RequireAuth`/`RequireRole` pehra dete hain (server bhi har call par role check karta hai).

### Asal code — har 5 second refresh `QueuePage.tsx`
```tsx
const query = useQuery({
  queryKey: ["incidents"],
  queryFn: ({ signal }) => listIncidents(client, {}, signal),
  refetchInterval: QUEUE_REFRESH_MS,          // 5000
  refetchIntervalInBackground: false,          // tab chhupa ho to ruk jao
});
```
**Matlab:** **TanStack React Query** khud data lata hai, cache karta hai, aur har 5 s dobara (WebSocket baad mein).

### Asal code — 3 click aur Confirm `DispatchPanel.tsx` (khayal)
```tsx
<button … onClick={() => { setProblem(null); setOpen(true); }}>{t("dsp.approve")}</button>   // click 2: sirf dabba
…
async function confirm() {                                                                    // click 3
  if (inFlight.current || chosen.length === 0) return; // one request per press
  …
  await mutation.mutateAsync(chosen);           // POST /incidents/{id}/dispatch
  setDone(chosen.map(plate));                    // "Dispatched: …" + "inform the driver"
  …
  } catch (error) {
    setProblem(problemFrom(error, errorText));   // 409 → "Use SIM-AMB-01 instead"
```
**Matlab:** Approve sirf khulasa kholta hai; **Confirm ke baghair kuch nahi jata**. 409 aaye to next-best ka button jo gaari badal deta hai. Kamyabi sirf 201 par.

### Asal code — pehle se tick `selection.ts`
```ts
export function preselect(incident, vehicles): Set<number> {
  const recs = [...(incident.recommendations ?? [])].sort((a, b) => a.rank - b.rank);
  if (!recs.length || openAssignments(incident).length > 0) return new Set();
  …
  for (const r of recs) {
    if (r.is_spare || (wanted[r.vehicle_type] ?? 0) <= 0) continue;
    if (blockReason(vehicles.get(r.vehicle_id))) continue;
    picked.add(r.vehicle_id);
    wanted[r.vehicle_type] = (wanted[r.vehicle_type] ?? 0) - 1;
  }
  return picked;
}
```
**Matlab:** AI ne jitni gaariyan "zaroori" kahin, har type ki utni sab se upar wali **available, non-spare** gaariyan tick; koi gaari pehle se raste mein ho to kuch tick nahi (backup dispatcher ka faisla).

### Asal code — safar ka haal `TripList.tsx`
```tsx
export function tripState(t, a): string {
  switch (a.status) {
    case "accepted":
      if (a.at_hospital_at) return t("trip.state.at_hospital");
      if (a.picked_up_at) return t("trip.state.picked_up");
      if (a.on_scene_at) return t("trip.state.on_scene");
      return t("trip.state.accepted");
    case "declined": …  // "Declined: too far"
    …
```
**Matlab:** assignment ke status aur waqton se card ka haal; 60 s se `approved` ho to "No answer from the driver" yaad-dihani (asli timeout baad mein).

---

## Tests kahan hain (har hissa)
| Hissa | Tests |
|---|---|
| 1 | `backend/tests/api/test_auth.py`, `test_rbac_matrix.py`, `test_api_contract.py`, `test_health.py`; `tests/unit/test_security.py`, `test_models_metadata.py`, `unit/schemas/*`; `tests/integration/test_schema.py`, `test_migrations.py`, `test_settings_service.py`, `test_audit_service.py`, `test_seed.py` |
| 2 | `backend/tests/api/test_reports.py` |
| 3 | `backend/tests/unit/agents/*` (gateway, triage, trust, policy, resource, orchestrator, worker, AI schemas), `tests/unit/test_pipeline_store_interface.py`, `tests/integration/test_pipeline_store.py`, `test_pipeline_end_to_end.py` |
| 4 | `backend/tests/api/test_incidents.py` |
| 5 | `backend/tests/api/test_dispatch.py`, `tests/integration/test_dispatch_concurrency.py` |
| 6 | `backend/tests/api/test_assignments.py` |
| 7 | `frontend/pwa/src/**/*.test.ts(x)`, `frontend/shared/src/**/*.test.ts(x)` |
| 8 | `frontend/dashboard/src/**/*.test.tsx` |

Chalana: `python3 scripts/run_project.py test` (backend) aur `python3 scripts/run_project.py test-web` (frontend).

---

## Code padhne ka tareeqa (mashwara)
1. `backend/app/main.py` → kaunse routers hain.
2. Ek report ka safar: `api/routes/reports.py` → `services/intake.py` → `workers/ai_worker.py` → `agents/orchestrator.py` → `agents/triage.py` → `llm/openai_compatible.py` → `agents/trust.py` → `agents/resource.py` → `services/pipeline_store.py` (save).
3. Dispatcher ka safar: `frontend/dashboard/src/incidents/QueuePage.tsx` → `IncidentPage.tsx` → `dispatch/DispatchPanel.tsx` → `api/routes/dispatch.py` → `services/dispatch.py`.
4. Driver: `api/routes/driver.py` → `services/assignments.py` → `schemas/assignment.py` (C-7).
5. Har file ke upar ki docstring pehle padhein; phir us ka test file — test batata hai ke code se **kya ummeed** hai.

## Chhoti lughat
| Lafz | Matlab |
|---|---|
| Endpoint / route | ek URL jo API sunti hai (`POST /api/v1/reports`) |
| Schema (Pydantic) | data ki tay shuda shakal; ghalat data → 422 |
| ORM / model | Python class jo database table hai |
| Migration | database ki tabdeeli ka script (Alembic) |
| Transaction / commit | sab ek saath save, ya kuch nahi |
| Row lock (`FOR UPDATE`) | ek row par "pehle main" — doosra intezar kare |
| `SKIP LOCKED` | locked row chhor ke agli uthao (worker) |
| LLM | bara language model (Groq par `gpt-oss-120b`) |
| Prompt | model ko di gayi hidayat (`triage_v1.md`) |
| LangGraph node / edge | graph ka ek qadam / qadamon ka raasta |
| Transient error | waqti masla (timeout) — dobara koshish |
| Hook (React) | `useState`, `useQuery` jaisi React ki khaas function |
| Component | screen ka ek tukda (`<SeverityBadge />`) |
| SIMULATED | nakli test data — asli Rescue 1122 nahi |


---
---

# Hissa P — Supervisor ko kaise samjhayein (presentation guide)

Ye hissa batata hai ke supervisor ke saamne **kya, kis tarteeb mein, aur kaise** dikhana hai. Har slide ke saath **bolne wale jumle** Roman Urdu mein diye hain. Technical alfaaz (LangGraph, PostgreSQL, API waghera) waise hi bolein — supervisor yahi alfaaz samajhte hain.

> Sab numbers 2026-11-23 ke hain (`main` `901a374` + D-036 fix). Presentation se pehle **P12** wali tayyari zaroor karein, taake numbers aur demo taaza hon.

## P1 — Presentation ka dhaancha (15–20 minute)

| # | Slide / hissa | Waqt | Kya dikhana |
|---|---|---|---|
| 1 | Masla aur maqsad | 1 min | Ye system kyun |
| 2 | Kya bana hai (numbers) | 1 min | P3 ki table |
| 3 | Architecture | 2 min | Hissa A ka naqsha |
| 4 | AI agents | 3 min | Hissa 3: LangGraph graph, Triage, Trust, Allocation |
| 5 | Safety rules code mein | 2 min | P5 |
| 6 | **Live demo** | 6–8 min | P6 script |
| 7 | Code ki jhalak | 2 min | P7 ki 5 files |
| 8 | Testing aur quality | 1 min | P8 |
| 9 | Kya baaqi hai, agla qadam | 1 min | P9 |
| 10 | Sawal jawab | — | P10, Hissa Q |

## P2 — Ek minute mein project (shuru mein yahi bolein)

> "AMCEDS Sukkur ke liye ek AI-assisted emergency dispatch prototype hai. Shehri web page se emergency report karta hai. Report **pehle database mein save** hoti hai, phir ek AI worker usay padhta hai — hadse ki qisam, kitna sangeen, kitne log zakhmi, kaunsi zaban — aur har cheez ke saath batata hai ke use kitna yaqeen hai. Phir saaf rules se report par bharosa (trust) naapta hai aur qareeb tareen gaariyon ka mashwara deta hai. Dispatcher sab kuch dashboard par dekhta hai aur **aakhri faisla hamesha dispatcher ka hota hai**: dispatcher ki manzoori ke baghair koi gaari nahi jati. Saara data SIMULATED (nakli test data) hai."

**Yaad rakhne wali teen baatein:** "Report pehle save, AI sirf mashwara, faisla hamesha insaan ka." Ye shuru mein hi bol dein; baaqi sab inhi se nikalta hai.

## P3 — Kya bana hai (numbers)

| Cheez | Number |
|---|---|
| Batch 1 tasks (implementation plan) | **70 mein se 34 poore + 2 adhe** (~50%); poora plan 91 tasks |
| Merge hue pull requests | **22** (har group ek PR, sab tests ke saath) |
| API endpoints | **49** contract mein; **17 bane hue**, 32 imaandari se `501` (abhi nahi bane) |
| Backend automatic tests | **982 passed**, 3 skipped (docs folder ke baghair); poore repo ke saath **985 passed, 0 skipped** |
| Frontend automatic tests | **176 passed** (typecheck aur build saaf) |
| Database | 15 tables, 35 settings, triggers aur indexes jo safety rules khud lagu karte hain |
| AI | Groq `openai/gpt-oss-120b` — live chal raha hai; English, Urdu, Roman Urdu, Sindhi |

> "Ab tak Batch 1 ka taqreeban aadha kaam mukammal hai: shehri ki report se lekar gaari bhejne aur us ke safar ko track karne tak poora raasta shuru se aakhir tak chalta hai, aur taqreeban 1,100 automatic tests hain."

## P4 — Architecture kaise samjhayein

Hissa A ka naqsha dikhayein aur ye bolein:

> "Ye ek modular monolith hai: ek FastAPI backend, PostgreSQL/PostGIS database ke saath, aur usi code se ek alag AI worker process. Database hi job queue ka kaam bhi karta hai — nayi report ka `pipeline_state = pending` hota hai, PostgreSQL worker ko khabar (NOTIFY) deta hai, aur worker usay `FOR UPDATE SKIP LOCKED` se uthata hai, is liye do workers kabhi ek hi report nahi uthate. Do React web apps hain: shehri ka report page aur dispatcher ka dashboard. Language model ek chhoti si gateway ke peeche hai, is liye ek setting badal kar Groq se local Ollama model par ja sakte hain."

**Ye design kyun (agar supervisor poochein):**
- Microservices nahi — FYP ke liye zyada pechida; SDS bhi modular monolith kehta hai.
- Alag queue (RabbitMQ/Redis) nahi — PostgreSQL hi kaafi hai, ek service kam chalani padti hai, aur report save hote hi job ban jati hai (ek hi transaction).
- AI alag process mein — AI dheema ya band ho tab bhi report save hoti hai aur dashboard chalta hai.

## P5 — AI agents kaise samjhayein (sab se ahem slide)

Hissa 3.6 ka graph dikhayein:
```
START → geocoding → TRIAGE (LLM) → TRUST (rules) → coordination (baad mein) → ALLOCATION (rules) → finish
            ↑ awaaz ho to pehle speech-to-text (baad mein)      ↘ AI fail → END (manual mode)
```

> "Qadamon ko tarteeb se chalane ke liye hum **LangGraph** use karte hain — ye ek state graph hai. Har qadam (node) agle qadam se pehle apna nateeja database mein save karta hai, is liye baad mein koi masla ho to pehle ka nateeja zaya nahi hota.
> - **Triage Agent** sirf yahi hissa hai jo LLM use karta hai. Ye ek version wala prompt bhejta hai jis mein SIMULATED misalein hain, temperature 0 par sirf JSON maangta hai, aur **sirf 12 tay shuda keys** qabool karta hai — is liye model kabhi status nahi badal sakta ya gaari nahi bhej sakta. Jawab ghalat ho to ek dafa dobara poochta hai, phir bhi ghalat ho to report manual mode mein chali jati hai.
> - **Trust Scorer** jaan-boojh kar **rules par chalta hai, AI par nahi**: har point ki likhi hui wajah dispatcher ko dikhti hai, aur AI ka kam yaqeen kabhi report ko fake nahi banata.
> - **Resource Allocation Agent** SRS ki table se nikalta hai ke kitni aur kaunsi gaariyan chahiye, aur qareeb tareen available gaariyon ko tarteeb deta hai. ETA abhi seedhi lakeer se hai aur saaf *approximate* likha hota hai, jab tak road routing nahi aati.
> - Duplicate reports milane wala **Coordination Agent** agla AI hissa hai jo banana hai."

**Ahem nukte (agar poochein "AI par control kitna hai?"):**
- AI **sirf mashwara** deta hai — koi agent gaari lock ya dispatch nahi kar sakta (`orchestrator.py` mein dispatch ka koi call hi nahi).
- Model ka jawab Pydantic schema se guzarta hai; ghalat ho to qabool nahi.
- Report ka text prompt mein **quote** hota hai — "ignore the rules" jaisi chaal se rules nahi badalte.
- Har AI nateeja audit log mein, model ke naam aur prompt version ke saath.
- LangChain ke "khud faisla karne wale agents/tools" jaan-boojh kar **use nahi** kiye — emergency system mein tay shuda aur jaanchne layak qadam chahiye.

## P6 — Live demo ka script (6–8 minute)

**Pehle se (P12):** backend aur web chal rahe hon, **Tayyari SQL** chala chuke hon (testing guide 1.5), do browser windows: ek report page (http://localhost:5174), ek dashboard (http://localhost:5173, `dispatcher1` logged in). Ek tab mein http://localhost:8000/docs (driver ke liye).

| Qadam | Aap kya karein | Kya bolein |
|---|---|---|
| 1 | Report page par 1122 notice dikhayein; **اردو** dabayein, phir English | "Page par hamesha 1122 ka notice hota hai, aur ye Urdu mein right-to-left bhi chalta hai." |
| 2 | Report likhein: `SIMULATED: Military Road par truck aur car ki takkar, 5 log zakhmi`, **Use my location**, jagah `Military Road`, naam, phone `0300 1234567` (teeno zaroori), **Send** | "Jagah, naam aur 11 hindson ka phone zaroori hain taake dispatcher wapas call kar sake. Reference number sirf tab aata hai jab database report save kar chuka ho." |
| 3 | Dashboard par jayein — 5–10 s mein card "AI is reading…" se nateeje mein badalta hai | "AI worker ne report khud utha li; queue har 5 second refresh hoti hai aur critical report sab se upar aati hai." |
| 4 | Card kholein: AI values + confidence, trust ki wajah, gaariyan + "≈ Approximate" | "AI ki har value ke saath us ka yaqeen dikhta hai; 60% se kam ho to likha aata hai ke dispatcher khud check kare. Trust mein har rule dikhta hai jis ne points diye ya kaate." |
| 5 | **Approve dispatch** → khulasa → **Confirm** | "Teen click. Confirm ke baghair kuch nahi jata. Gaari isi lamhe lock hoti hai, mashwara dene par kabhi nahi." |
| 6 | (Optional, sab se asar daar) doosri window mein `dispatcher2` se wahi gaari Confirm | "Agar do dispatcher ek hi gaari chunein to sirf ek kamyab hota hai; doosre ko agli behtar gaari offer hoti hai." |
| 7 | `/docs` mein driver (`driver05`) se **accept**, phir **on_scene** | "Driver app abhi nahi bani, is liye main API se driver ka kaam kar raha hoon." |
| 8 | Dashboard ka card khud "On scene" ho jata hai; **Change hospital** dikhayein | "Dispatcher ko safar ka haal bina reload ke dikhta hai." |
| 9 | Driver se **available** → report **Closed** | "Aakhri safar khatam hote hi report khud band ho jati hai aur gaari dobara free." |
| 10 | (30 s) database mein audit query (testing guide Hissa 10) | "Har AI nateeja aur har faisla audit log mein hai jise badla nahi ja sakta — UPDATE bhi fail hota hai." |

**Agar demo mein kuch ghalat ho jaye:**
- AI jawab na de → "Yahi to safety design hai: report save hai aur manual mode mein chali gayi." Phir manual mode se dispatch dikha dein (testing guide 8.5).
- Gaari ka mashwara na aaye → 60 s guzar gaye; Tayyari SQL dobara chalayein aur nayi report bhejein.
- Pehle se taiyar ek report rakhein (P12) taake intezar na karna pade.

## P7 — Code dikhana ho to ye 5 files kholein

| File | Kya dikhayein (1–2 min) |
|---|---|
| `backend/app/agents/orchestrator.py` → `_build()` | LangGraph graph: nodes aur edges |
| `backend/app/agents/triage.py` → `run()` aur `_clean()` | LLM call, sirf 12 keys, ek retry, `TriageFailed` |
| `backend/app/agents/prompts/triage_v1.md` | Prompt aur "Never guess / Never invent a location" rules |
| `backend/app/services/dispatch.py` → `approve()` | Row lock, fake/closed ka inkaar, AI vs dispatcher ka audit |
| `backend/migrations/versions/0002_initial_schema.py` | `uq_assignments_open_vehicle` index aur audit trigger |

Frontend dikhana ho: `frontend/dashboard/src/dispatch/DispatchPanel.tsx` (Approve → Confirm).

## P8 — Testing aur quality kaise batayein

> "Har group tests ke saath bana aur tabhi merge hua jab tests pass hue: taqreeban 985 backend tests Docker mein asli PostGIS database par chalte hain, aur 176 frontend tests. Har group ke liye maine mutation check bhi kiya — jaan-boojh kar code tod kar dekha ke koi test fail hota hai — aur asli API aur Groq model ke saath live check bhi. Do dispatchers ka ek saath ek gaari chunna asli database par 50 dafa test hota hai."

Saath mein imaandari se bata dein:
- Tests **nakli (fake) model** se chalte hain taake tez aur bina internet ke hon; asli Groq har group ke **live check** mein chalaya gaya.
- CI (GitHub Actions) sirf backend tests chalata hai; frontend tests abhi local.
- Har kaam ka record: `STATUS.md`, `CHANGES.md`, `DECISIONS_LOG.md`.

## P9 — Kya baaqi hai aur agla qadam

| Baaqi | Kyun ahem | Task |
|---|---|---|
| Driver duty aur GPS, live fleet | gaariyon ki asal jagah; abhi SIMULATED SQL | B1-A1-27 |
| Scheduler: 60 s jawab timeout, signal lost | TC-28; faisla **D-029 manzoori ka intezar** | B1-A1-28 |
| WebSocket live updates | abhi 5 s polling | B1-A1-29 |
| Driver ko alert, driver mobile app | abhi dispatcher "inform the driver" | B1-A1-30, B1-A3-13…17 |
| Coordination Agent (duplicate reports) | ek hadse ki kai reports | B1-A2-08/09 |
| Geocoding (jagah ke naam se), OSRM routes | abhi GPS aur seedhi lakeer | B1-A2-05, B1-A2-10 |
| Awaaz/SMS reports | speech-to-text | B1-A1-17, B1-A2-04 |
| Review queue, admin panel, analytics | Real/Fake faisla, settings, reports | B1-A1-23, 31, 32 |
| AI ki durusti ka evaluation | triage kitna sahi hai, naapna | B1-A2-17 |

> "Bunyadi chakkar (report → AI → dispatch → safar) chal raha hai. Agla qadam driver duty aur GPS hai, saath jawab ke timeout ke liye scheduler; phir live WebSocket updates, duplicate pehchanne wala agent aur driver app."

## P10 — Supervisor ke mumkina sawal aur jawab

| Sawal | Jawab |
|---|---|
| Kaunsa AI framework use kiya? | Qadamon ko state graph ki shakal mein chalane ke liye LangGraph; model Groq ka `gpt-oss-120b`, us ki OpenAI-compatible HTTP API se, hamari apni chhoti gateway ke zariye. LangChain ke agents ya tools nahi. |
| AI ko seedha gaari bhejne kyun nahi dete? | Insaan ka faisla (human-in-the-loop) bunyadi shart hai (SRS NFR-S1). AI sirf mashwara deta hai; sirf logged-in dispatcher ka Confirm assignment banata hai, aur wo audit hota hai. |
| AI ghalat ho to? | Har value ke saath yaqeen dikhta hai; 60% se kam par screen kehti hai dispatcher khud check kare. Dispatcher doosri gaariyan chun sakta hai; audit mein AI ka mashwara aur dispatcher ka chunao dono record hote hain. |
| AI ya internet band ho to? | Report kisi bhi AI qadam se pehle save hoti hai. Model fail ho to report "needs check" + "AI failed" mein jati hai, trust phir bhi banta hai, aur dispatcher haath se gaari bhejta hai. Ye test hua hai. |
| Trust rules par kyun, AI par kyun nahi? | Ye samajh mein aane wala aur insaf wala hona chahiye: har point ki likhi hui wajah hai, aur AI ka kam yaqeen kabhi report ko fake nahi bana sakta. |
| Report ke text se model ko dhoka kaise nahi diya ja sakta? | Report user message mein quote hoti hai, sirf 12 tay keys qabool hoti hain, values Pydantic se jaanchi jati hain, aur model ke paas status badalne ka koi raasta hi nahi. |
| Do dispatcher ek hi ambulance chunein to? | PostgreSQL ke row lock aur partial unique index: ek kamyab, doosre ko 409 aur agli behtar gaari. Asli database par 50 dafa test hua. |
| Kya ye Urdu mein chalta hai? | Haan — report page do zabaanon mein hai, Urdu right-to-left; triage English, Urdu script, Roman Urdu aur Sindhi samajhta hai. |
| Kya data asli hai? | Nahi. Sab SIMULATED hai; Rescue 1122 se koi asli talluq nahi. |
| AI kitna sahi hai? | SIMULATED reports par haath se check kiya; baqaida evaluation set ek planned task hai (B1-A2-17). Misaal: "5 zakhmi, 2 behosh" ko model ne 7 gina — isi liye yaqeen dikhate hain. |
| ETA kaise nikalta hai? | Seedhi lakeer ki doori ek tay speed par, hamesha "approximate" likha; OSRM road routing planned hai. |
| Kaise pata ke ye chalta hai? | Taqreeban 1,100 automatic tests, mutation checks, live shuru-se-aakhir checks; testing guide har qadam aur us ka sahi output batati hai. |
| RabbitMQ/Kafka ki jagah database queue kyun? | Kam cheezein chalani padti hain; report aur us ki job ek hi transaction mein save; `SKIP LOCKED` se workers mehfooz tareeqe se saath chalte hain. |
| Model badal sakte hain? | Haan, `.env` mein `LLM_PROVIDER`/`LLM_MODEL` badal kar — Groq ya local Ollama. (Groq ne `llama-3.3-70b-versatile` band kiya to isi tarah `gpt-oss-120b` par gaye.) |
| Privacy aur security? | Password bcrypt hash, chhote JWT tokens jo sirf memory mein rehte hain, har endpoint par role check, 5 ghalat password par account lock, 30 minute idle logout, secrets sirf `.env` mein. |
| Kya baaqi hai? | P9 dekhein — pehle driver duty/GPS aur scheduler, phir WebSocket, duplicates, driver app. |

## P11 — Kya dava (claim) NAHI karna
- "Driver ko alert jata hai" — **nahi**, abhi dispatcher khud batata hai.
- "Driver app bani hui hai" — **nahi**, driver ke kaam API (`/docs`) se.
- "60 second ka timeout chalta hai" — **nahi**, sirf screen par yaad-dihani.
- "ETA road ke hisaab se hai" — **nahi**, seedhi lakeer, "approximate".
- "AI ki accuracy X% hai" — abhi naapi nahi gayi.
- "Duplicate reports milaye jate hain" — **nahi**, Coordination Agent baqi hai.
- "Live map hai" — **nahi**.
- "Real data / Rescue 1122 se juda hai" — **nahi**, sab SIMULATED.
- "Audit ko database ka koi bhi user nahi badal sakta" — **nahi**, app ka database user owner/superuser hai (Hissa Q1.12).

Ye imaandari supervisor ko achhi lagti hai: jo bana hai wo **chala kar dikhayein**, jo nahi bana wo `501` aur roadmap se dikhayein.

## P12 — Presentation se ek din pehle ki tayyari
1. `git checkout main && git pull` — taaza code.
2. `python3 scripts/run_project.py` aur `python3 scripts/run_project.py web` — dono chal jayein (masle: testing guide 2.4).
3. `python3 scripts/run_project.py test` aur `test-web` — **0 failed** (naye numbers P3 mein likh lein).
4. Testing guide ki **Tayyari SQL** (1.5) chalayein; ek report pehle se bhej kar AI ka nateeja tayyar rakhein.
5. Demo (P6) ek dafa poora chala kar dekhein; browser windows aur `/docs` tab pehle se khol kar rakhein.
6. `.env` mein Groq key aur model check: start par "Groq key works and model … is available".
7. Internet na ho to: manual mode wala demo (AI fail → report bachi → manual dispatch) — ye bhi ek mazboot point hai.
8. Ye files saath rakhein: `docs/CODE_WALKTHROUGH.md` (ye file), `docs/MANUAL_TESTING_GUIDE.md`, `STATUS.md`.

---
---

# Hissa Q — Aur sawal: code aur database (supervisor ke liye)

Har sawal ke saath: **jawab** (bolne ke liye), aur **Kahan** (code/file) ya **Saboot** (SQL jo supervisor ke saamne chala sakte hain). Database kholne ka tareeqa: `docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`.

## Q0 — Database ka naqsha (pehle ye dikhayein)

PostgreSQL 15 + **PostGIS** extension. **15 tables**, 35 CHECK constraints, 18 foreign keys, 3 spatial (GiST) indexes. Banaya **Alembic migrations** ne: `0001` (PostGIS on) → `0002` (saari tables, indexes, triggers) → `0003` (35 settings).

```
 callers ──1:N──► incidents ◄──N:1── incident_groups            users ──1:N──► user_sessions
 (phone/device)     │  (report + AI nateeje + status)              │ (role: admin/dispatcher/driver)
                    │                                              │ 1:1 (driver_id)
                    ├──1:N──► recommendations ──N:1──► vehicles ◄──┘
                    │         (AI ka mashwara, round)      │  ├──1:N──► vehicle_locations (GPS, abhi khaali)
                    ├──1:N──► assignments ─────N:1─────────┘  │
                    │         (bheji gayi gaari, safar)  ──N:1──► hospitals
                    ├──1:N──► duplicate_candidates (incident ↔ incident)
                    ├──1:N──► confirmation_requests
                    └──1:N──► audit_logs (har qadam; badla nahi ja sakta)

 settings (35 key/value)      worker_heartbeats (AI worker zinda hai?)
```

| Table | Kya rakhti hai | Kis hisse ne use ki |
|---|---|---|
| `incidents` | Report: asli text, channel, jagah (PostGIS point), AI nateeje (type, severity, victims, confidence), trust, status, `pipeline_state`, review reasons, `settings_snapshot` | Hissa 2, 3, 4 |
| `callers` | Report bhejne wala (phone ya device), purani asli/fake reports ki ginti | Intake, Trust |
| `users`, `user_sessions` | Accounts (bcrypt hash, role, on_duty, lock) aur har login ka session (idle, logout) | Hissa 1 |
| `vehicles`, `hospitals` | Gaariyan (type, status, driver, aakhri GPS) aur hospitals (point) | Hissa 3, 5, 6 |
| `recommendations` | AI ka mashwara: rank, ETA, doori, `is_spare`, `batch_no`/`is_current` (round) | Hissa 3, 4 |
| `assignments` | Bheji gayi gaari: kisne/kab approve, har safar qadam ka waqt, decline ki wajah | Hissa 5, 6 |
| `audit_logs` | Har AI nateeja, faisla, status ki tabdeeli, login | sab |
| `settings` | 35 SRS settings (trust points, 60 s limits, …) | Hissa 1, 3 |
| `incident_groups`, `duplicate_candidates`, `confirmation_requests` | Duplicates aur caller se tasdeeq | tables bani hain, features baad mein |
| `vehicle_locations` | GPS ki history | B1-A1-27 mein |
| `worker_heartbeats` | AI worker ka haal (har 10 s) | Hissa 3 |

## Q1 — Database ke sawal

**1. Kaunsa database aur kyun?**
PostgreSQL 15, PostGIS ke saath. Is mein transactions aur row locks hain (mehfooz dispatch ke liye zaroori), AI details ke liye JSONB, aur doori ke liye spatial types/functions — sab ek hi service mein. *(SDS §4.2 bhi yahi kehta hai.)*

**2. Tables kaise banti aur badalti hain?**
Alembic migrations se, `backend/migrations/versions/` mein. `app/models/` ki SQLAlchemy classes se migration `0002` khud bani aur phir haath se jaanchi gayi; triggers haath se likhe gaye. Shuru mein `alembic upgrade head` chalta hai (launcher khud chalata hai).
**Saboot:** `SELECT version_num FROM alembic_version;` → `0003`.

**3. Code database se kaise baat karta hai?**
SQLAlchemy 2 **async** mode mein, asyncpg driver ke saath (`app/core/db.py`: `create_async_engine(…, pool_pre_ping=True)`). Har HTTP request ko apna session milta hai (`app/api/deps.py` ka `get_db`); service kaam karti hai aur route aakhir mein ek dafa commit karta hai. Kuch bhi fail ho to rollback — aadha save kuch nahi hota.

**4. Jagah kaise store hoti hai? Doori kaise nikalti hai?**
`geometry(Point, 4326)` columns (`incidents.location`, `vehicles.last_location`, `hospitals.location`), GeoAlchemy2 ke zariye. Doori PostGIS zameen ki golai ke hisaab se nikalta hai: `ST_Distance(a::geography, b::geography)`, aur "N meter ke andar" ke liye `ST_DWithin(…)` (`services/pipeline_store.py`, `services/dispatch.py`). Allocation agent ETA ke liye Python mein haversine bhi use karta hai.
**Saboot:**
```sql
SELECT indexname FROM pg_indexes WHERE indexdef ILIKE '%gist%';
-- idx_hospitals_location, idx_incidents_location, idx_vehicles_last_location
```

**5. Reference number kaise banta hai?**
PostgreSQL ka **generated column** jo save hui row se khud banta hai: `'INC-' || lpad(incident_id::text, 6, '0')`. Is liye reference number sirf tab hota hai jab row save ho chuki ho (safety rule 1). *(`app/models/incident.py`, `REFERENCE_NO_SQL`.)*

**6. Kaise pakka hai ke report AI se pehle save hoti hai?**
API incident ko `pipeline_state = 'pending'` ke saath insert karti hai, audit row aur `pg_notify('report_pending', id)` likhti hai — sab **ek transaction** mein — commit karti hai, aur sirf us ke baad 201 deti hai. PostgreSQL NOTIFY sirf commit ke baad bhejta hai, is liye worker kabhi bina save hui report nahi dekh sakta. *(`services/intake.py`.)*

**7. Database ko hi job queue kyun banaya?**
Report aur us ki job ek hi row hai, ek saath save — job kabhi gum nahi ho sakti, aur bina report ke job nahi ho sakti. Koi extra service (Redis/RabbitMQ) nahi chalani padti. Worker `LISTEN report_pending` se jaagta hai aur har 2 s khud bhi dekhta hai.
**Saboot:** `SELECT reference_no, pipeline_state, pipeline_attempts FROM incidents ORDER BY incident_id DESC LIMIT 5;`

**8. Do workers — kya ek hi report utha sakte hain?**
Nahi. Worker `UPDATE … SET pipeline_state='processing'` ke andar `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` se report uthata hai: ek worker ki locked row doosra chhor kar agli uthata hai. Critical reports pehle uthayi jati hain. Partial index `ix_incidents_pipeline_waiting` (sirf `pending`/`reallocate` rows) isay tez rakhta hai. Asli database par do workers ke saath test hua. *(`pipeline_store.claim_next`.)*

**9. Worker beech mein crash ho jaye to?**
Row `processing` hi rehti hai. Har 60 s `requeue_stale_jobs` 10 minute se zyada phansi rows ko wapas `pending` kar deta hai; 3 koshishon ke baad report manual mode mein (`ai_failed`). Kuch zaya nahi hota.

**10. Ek ambulance do jagah jane se kaise rokte hain?**
Teen tehein: (1) dispatch service gaariyon ki rows ko id ki tarteeb mein `FOR UPDATE` lock karti hai aur khuli assignment check karti hai; (2) sab ek transaction mein; (3) **partial unique index** `uq_assignments_open_vehicle ON assignments(vehicle_id) WHERE status IN ('approved','accepted')` doosri khuli assignment ko namumkin bana deta hai, chahe code mein koi bug ho. Do dispatchers ke saath 50 rounds test hue.
**Saboot:**
```sql
SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_assignments_open_vehicle';
```

**11. "Id ki tarteeb" mein lock kyun?**
Agar dispatcher A gaari 3 phir 5 lock kare aur B gaari 5 phir 3, to dono hamesha ek doosre ka intezar karte rahenge (deadlock). Hamesha chhoti id pehle (aur har jagah incident → vehicle → assignment) lock karne se ye nahi hota.

**12. Kaise pakka hai ke audit log badla nahi ja sakta?**
Database triggers: `audit_logs_no_modify` (UPDATE ya DELETE se pehle) aur `audit_logs_no_truncate` error dete hain, is liye na application aur na aam SQL `UPDATE`/`DELETE`/`TRUNCATE` history badal sakta hai. Ek aur trigger, `incidents_keep_original`, asli report ka text/audio sirf ek dafa likhne deta hai.
*Imaandar had:* is prototype mein app database ke owner (superuser `dispatch`) ki tarah judi hai, aur owner jaan-boojh kar trigger hata sakta hai; production mein app ke liye kam ikhtiyar wala alag database user hona chahiye (abhi nahi bana).
**Saboot:**
```sql
UPDATE audit_logs SET action = 'x' WHERE log_id = (SELECT max(log_id) FROM audit_logs);
-- ERROR:  audit_logs rows cannot be changed or deleted (NFR-C10)
```

**13. Audit log mein kya likha jata hai?**
Report aana; har AI qadam (`ai.geocode`, `ai.triage`, `ai.trust`, `ai.allocation`, `ai.failed`); dispatch, AI ki list aur dispatcher ke chunao ke saath; gaari ka lock/unlock; assignment ka har qadam; login, ghalat login, account lock, logout; naye users. Tabdeeli ke **usi transaction** mein, is liye bina audit ke koi tabdeeli nahi hoti. *(`services/audit.py`.)*
**Saboot:** `SELECT action, count(*) FROM audit_logs GROUP BY 1 ORDER BY 2 DESC;`

**14. Allowed values (status, severity, type…) kaise lagu hoti hain?**
Ye `text` columns hain jin par **CHECK constraints** hain, jo Python enums (`app/schemas/enums.py`) se bane, masalan `status IN ('new','triaged','needs_check','dispatched','on_scene','closed','fake')`. Kul 35 CHECK constraints (confidence 0–1, trust 0–100, victims ≥ 0, report mein text ya audio hona zaroori bhi).
**Saboot:** `SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname LIKE 'ck_incidents_status%';`

**15. PostgreSQL ENUM ki jagah text + CHECK kyun?**
PostgreSQL ENUM mein nayi value daalne ke liye khaas migration chahiye; CHECK constraint badalna aasaan hai aur hifazat wahi deta hai (faisla D-005).

**16. AI ke nateeje kahan save hote hain?**
Ahem values aam columns mein (`incident_type`, `severity`, `victims_estimate`, `confidence`, `language`, `trust_score`, `trust_tier`) taake tarteeb aur filter tez hon; AI ka poora jawab **JSONB** mein (`ai_details` = triage ka nateeja, har field ka yaqeen, model ka naam, prompt version, waqt; `trust_signals`; `allocation_summary`). Gaariyon ke mashware apni alag table mein.
**Saboot:** `SELECT jsonb_pretty(ai_details) FROM incidents WHERE ai_details IS NOT NULL ORDER BY incident_id DESC LIMIT 1;`

**17. `settings_snapshot` kya hai?**
Report aate hi us waqt ki saari 35 settings incident mein copy ho jati hain (JSONB). AI aur trust rules wahi snapshot use karte hain, is liye admin baad mein koi setting badle to purani reports par asar nahi hota (SRS UC-12).

**18. `recommendations.batch_no` aur `is_current` kyun?**
Ek report ka mashwara baad mein dobara ban sakta hai (naya round). Purane round history ke liye rehte hain (`is_current = false`); screens sirf maujooda round dikhati hain.

**19. "Dobara bhejne par wahi reference" database mein kaise chalta hai?**
`incidents.client_request_id` par UNIQUE constraint hai. Wahi id dobara aaye to purani row mil jati hai (200, wahi reference); agar do copy bilkul ek saath aayein to doosri insert unique constraint se takrati hai aur route pehli wali lauta deta hai.

**20. Login sessions kaise store hote hain? Sirf JWT kyun nahi?**
Har login par `user_sessions` ki row banti hai (`session_id` = token ka `jti`, `last_activity_at`, `revoked_at`). Har request par ye check hoti hai, is liye logout, 30 minute idle aur band kiya gaya account foran session khatam karte hain — sirf JWT ho to usay beech mein band nahi kiya ja sakta.

**21. Password kaise store hote hain?**
`users.password_hash` mein sirf bcrypt hash; ghalat password ki ginti aur `locked_until` columns se 5 koshish / 15 minute lock lagta hai.

**22. "Available gaari" SQL mein kaise nikalti hai?**
Status `available`, koi khuli assignment nahi, driver active **aur** on duty, aur GPS `signal_lost_s` (60 s) ke andar aayi ho: `… AND u.on_duty AND v.last_seen_at >= now() - make_interval(secs => :lost) AND NOT EXISTS (SELECT 1 FROM assignments …)`. *(`pipeline_store.list_available_vehicles`.)*

**23. Kaunse indexes banaye aur kyun?**
`ix_incidents_status_severity` (queue), `ix_incidents_pipeline_waiting` (partial, worker ke liye), `ix_incidents_type_received_at` (qareeb ki same-type reports), `ix_audit_logs_incident_time` (ek report ki history), `ix_recommendations_incident_current`, `ix_vehicle_locations_vehicle_time`, GiST spatial indexes, aur unique/partial-unique wale (`uq_assignments_open_vehicle`, `uq_vehicles_driver_id`, caller ka phone/device, username, plate, client_request_id).

**24. Kya tests mera asli data chhoote hain?**
Nahi. Tests har dafa alag database `dispatch_test` naye sire se banate aur migrate karte hain; zyada tar tests ek transaction ke andar chalte hain jo aakhir mein rollback hota hai. Concurrency tests apna alag aarzi database use karte hain.

**25. Sample data kaise load hota hai? Kya do dafa ban sakta hai?**
`python -m app.seed --size small` (launcher khud chalata hai). Ye dobara chalane par kuch nahi dohrata: users username se, gaariyan plate se, hospitals naam se sirf tab daale jate hain jab maujood na hon. Passwords sirf `.env` se aate hain.

**26. Backup / reset?**
Data Docker volume `pgdata` mein rehta hai; `run_project.py stop` usay rakhta hai; `docker compose down -v` mita deta hai (testing guide mein warning hai). Production ka backup plan is prototype ka hissa nahi.

## Q2 — Backend code ke sawal

**1. FastAPI kyun?**
Async hai (database aur LLM ke intezar mein acha), Pydantic se request ki jaanch khud karta hai, aur `/docs` par OpenAPI/Swagger khud banata hai — usi se frontend ki TypeScript types bhi banti hain.

**2. Code kis tarah tarteeb diya gaya hai?**
Routes (HTTP) → services (business logic, ek transaction) → models (tables). Schemas (Pydantic) har request/response ki shakal tay karte hain. AI ka code alag hai (`agents/`, `llm/`, `workers/`). *(Hissa C.)*

**3. Input ki jaanch kaise hoti hai?**
Pydantic models `extra="forbid"` ke saath (anjaan fields mana), lambai, patterns (phone), had (lat/lon, confidence) aur fields ke aapas ke rules (lat aur lon saath). Ghalat input → 422 field ki tafseel ke saath; bheji gayi value wapas nahi dikhayi jati.

**4. Errors kaise lautaye jate hain?**
Hamesha `{code, message, details}` (`app/api/errors.py`). Codes jaise `validation_error`, `unauthorized`, `forbidden`, `not_found`, `vehicle_locked`, `invalid_transition`, `not_implemented`, `service_unavailable`.

**5. Aap ki API mein 501 ka kya matlab hai?**
Endpoint tay shuda contract (`docs/API_CONTRACT.md`) mein hai lekin abhi bana nahi; ye kabhi nakli data nahi deta. 49 mein se 32 abhi 501 hain.

**6. Roles kaise lagu hote hain?**
Har private route par FastAPI dependencies (`app/api/deps.py` ka `require_roles`); role har request par database se padha jata hai, token par bharosa nahi. Ek test matrix har route × har role check karta hai (`tests/api/test_rbac_matrix.py`).

**7. "Contract" (C-1 … C-7) kya hai?**
Backend, AI aur frontend ke beech tay shuda shakalein: C-1 incident record, C-2 AI nateeje, C-3 login, C-4 endpoints ki list, C-5 events, C-6 pipeline store ka interface, C-7 driver ki assignment aur safar ke allowed qadam. Tabdeeliyan `DECISIONS_LOG.md` mein version ke saath (masalan C-1 v1.2 mein `plate_number` aaya).

**8. Assignment ki state machine kaise chalti hai?**
C-7 allowed qadam tay karta hai (`app/schemas/assignment.py` mein `ASSIGNMENT_TRANSITIONS`, `TRIP_TRANSITIONS`); service har qadam ko is se check karti hai aur baaqi ko 409 se mana karti hai, kuch badle baghair. *(Hissa 6.)*

**9. Configuration aur secrets kaise sambhale jate hain?**
`pydantic-settings` `.env` padhta hai (`app/core/config.py`). Secrets (DB password, JWT secret, Groq key, seed passwords) sirf `.env` mein, jo git mein nahi jati; dev ke ilawa API kamzor JWT secret ke saath shuru hi nahi hoti.

**10. Ise chalate kaise hain?**
Docker Compose: `postgres`, `api` (Uvicorn), `ai-worker`. `scripts/run_project.py` `.env` check karta hai, services chalata hai, health ka intezar karta hai, Groq model check karta hai, migrations aur seed chalata hai, aur worker ka log dikhata hai.

## Q3 — AI code ke sawal

**1. "Agent" asal mein kahan hai?**
`app/agents/triage.py` (LLM), `trust.py` aur `policy.py` (rules), `resource.py` (rules + doori), jinhein `orchestrator.py` (LangGraph) jorta hai aur `workers/ai_worker.py` chalata hai. *(Hissa 3.)*

**2. LangGraph yahan kya karta hai jo ek saada function nahi karta?**
Ye pipeline ko ek saaf **state graph** bana deta hai: naam wale nodes, shart wale raaste (awaaz → pehle speech-to-text; triage fail → khatam), mushtarka state, aur aane wale qadam (speech-to-text, geocoding, coordination) aasaani se daalna, poora flow dobara likhe baghair. SDS bhi orchestrator ke liye LangGraph kehta hai.

**3. LangChain ke agents aur tools kyun nahi?**
Khud mukhtar agent apne qadam khud chunta hai; emergency system ko tay shuda, test ho sakne wale qadam chahiye aur model ko kabhi koi action lene nahi dena. Is liye model sirf report ko *bayan* karta hai; baaqi har faisla code karta hai.

**4. Prompt dikhayein. Output kaise qaboo mein rakhte hain?**
`app/agents/prompts/triage_v1.md`: 12 JSON keys ki tay list, allowed values, rules ("Use null… Never guess", "Never invent a location"), severity ki tareefein aur chaar SIMULATED misalein. Call temperature 0 aur JSON mode mein; jawab `_clean` se saaf aur Pydantic (`TriageResult`) se jaancha jata hai. Har nateeje ke saath prompt version save hota hai.

**5. Model ka jawab ghalat ho to kya hota hai?**
Ek dafa dobara, model ko ghalti bata kar; phir bhi ghalat → `TriageFailed` → report `needs_check` + `ai_failed` (manual mode). Timeout / 429 / 5xx par orchestrator wqfe (backoff) ke saath do dafa dobara koshish karta hai.

**6. Zaban kaise pehchani jati hai?**
Model batata hai; saath `script_language()` Arabic script aur Latin huroof gin kar ishara deta hai (Urdu, Sindhi agar Sindhi ke khaas huroof hon, Mixed). Latin text (English ya Roman Urdu) ka faisla model karta hai.

**7. Kitni gaariyan chahiye, ye kaise nikalta hai?**
`agents/resource.py` ka `vehicles_needed()` SRS Table 7.3.3 lagu karta hai: ambulances = zakhmi ÷ ek ambulance ke mareez (upar ki taraf round), kam az kam 1; aag mein fire truck aur backup; critical accident mein backup; type maloom nahi → dispatcher chunega. Saath 2 spare, qareeb pehle.

**8. Trust kaise nikalta hai? Kya AI report ko fake bana sakta hai?**
`agents/trust.py`: 50 se shuru, har rule ke points wajah ke saath jorna/ghatana, 0–100 ke andar, settings ki hadon se tier. AI ka yaqeen input hi **nahi**, is liye kam yaqeen kabhi report ko fake nahi bana sakta (D-012); fake sirf dispatcher mark kar sakega (baad ka task).

**9. Local model par ja sakte hain?**
Haan: `.env` mein `LLM_PROVIDER=ollama` aur `LLM_MODEL=…` (`app/llm/ollama.py`). Baaqi code nahi badalta.

**10. API ke paise diye baghair AI code kaise test karte hain?**
`app/llm/fake.py` (`FakeLLMClient`) tay jawab deta hai; unit tests sahi, ghalat, retry, timeout aur prompt-injection ki haalatein check karte hain. Asli Groq model har group ke live check mein chalaya gaya.

**11. Ye kitna tez hai?**
Live checks mein Groq ke saath triage har report par taqreeban 2–3 second, poori pipeline taqreeban 3 second. Orchestrator har qadam ka waqt log karta hai (`timings_ms`).

**12. Report ka data Groq ko jana privacy ka masla hai?**
Asal istemal mein haan; yahan theek hai kyunke saara data SIMULATED hai (NFR-C7). Asli data ke liye Ollama (local) wala option report ko bahar nahi bhejta.

## Q4 — Frontend ke sawal

**1. Do web apps kyun?**
Shehri ka report page (`frontend/pwa`) halka hona chahiye aur bina login; dashboard (`frontend/dashboard`) staff ke liye, login aur roles ke saath. Dono ek mushtarka package use karte hain (`frontend/shared`: API client, UI kit, English/Urdu).

**2. Frontend backend ke saath kaise mel mein rehta hai?**
`npm run gen:api` backend ke `/openapi.json` se `shared/src/api/schema.ts` banata hai; `npm run gen:api:check` farq ho to fail hota hai. Backend ki koi tabdeeli jo screen tode, wo TypeScript compile par pakdi jati hai.

**3. Dashboard refresh kaise hota hai?**
TanStack React Query har 5 s poochta hai (queue, incident) aur tab chhupa ho to ruk jata hai; kisi action ke baad mutaliqa data refresh karta hai. WebSocket push B1-A1-29 ke saath aayega.

**4. Login token kahan rakhe jate hain?**
Sirf memory mein (`shared/src/api/tokens.ts`), kabhi `localStorage` mein nahi; reload par dobara login (shared computer par zyada mehfooz). 401 par client ek dafa refresh karta hai; wo bhi fail ho to user login par.

**5. Do dafa bhejne se kaise rokte hain?**
`useRef` ka "in flight" nishan aur band buttons; report page `client_request_id` bhi bhejta hai taake dobara bheji report ek hi dafa save ho.

**6. Urdu kaise chalti hai?**
`shared/src/i18n/en.json` aur `ur.json` (same keys, test check karta hai); Urdu chunne par page par `dir="rtl"`; text boxes `dir="auto"`.

## Q5 — Testing aur kaam ke tareeqe ke sawal

**1. Kitne tests aur kis qisam ke?**
Taqreeban 985 backend (unit, API, asli PostGIS par integration) aur 176 frontend (component aur behaviour tests, nakli backend ke saath).

**2. Mutation check kya hai?**
Tests likhne ke baad main jaan-boojh kar code todta hoon (masalan fake report ko dispatch hone deta hoon) aur dekhta hoon ke koi test fail hota hai; phir code wapas theek. Har group ki tod-phod pakdi gayi (kuch ek missing test add karne ke baad).

**3. Concurrency kaise test karte hain?**
`tests/integration/test_dispatch_concurrency.py`: do sessions ek hi waqt ek gaari approve karte hain, 50 rounds, asli commits; saath ek test ke sirf unique index bhi doosri khuli assignment rok deta hai.

**4. Testing mein bugs mile?**
Haan, aur sab `CHANGES.md` mein darj hain: masalan Groq ka band hua model, `.env` mein password ka farq, peeche chalta reh jane wala worker container, decline ke baad approval panel ki galti, waqt par mabni flaky test — har ek test ke saath theek kiya.

**5. Kaam ka record kaise rakha jata hai?**
`STATUS.md` (abhi ki halat), `CHANGES.md` (har tabdeeli tests ke saath), `DECISIONS_LOG.md` (faislay aur contract versions), `IMPLEMENTATION_PLAN.md` (tasks ka haal), `docs/API_CONTRACT.md`, `docs/MANUAL_TESTING_GUIDE.md`, aur ye file.

**6. Kaam merge kaise hota hai?**
Har group ki ek branch aur ek pull request (ab tak 22 merge); CI GitHub par backend tests chalata hai.
