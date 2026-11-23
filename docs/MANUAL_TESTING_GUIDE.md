# AMCEDS — Haath se testing ki guide (shuru se aakhir tak)

Ye guide **ab tak bana hua sab kuch** usi tarteeb mein test karwati hai jis tarah asal mein hota hai:

> shehri report bhejta hai → AI padhta hai → dispatcher dashboard par dekhta hai → gaari bhejta hai → driver ka safar → gaari wapas free.

Har step par **"Sahi output"** likha hai. Aap ka output us jaisa ho to wo hissa sahi chal raha hai.

- Har output asal mein chala kar likha gaya hai (2026-11-22/23). **Reference number, waqt aur id aap ke alag honge** — shakal wahi honi chahiye.
- **Sab data SIMULATED hai.** Reports mein `SIMULATED:` likhna acchi aadat hai.
- Kisi step mein output alag aaye to us ka **command aur poora output** copy karke bhejein.

---

## Hissa 0 — Kya bana hai aur kya abhi nahi bana

| Kya | Haal | Hissa |
|---|---|---|
| Ek command se project chalana (`scripts/run_project.py`) | ✅ | 2 |
| Database: 15 tables, 35 settings, SIMULATED sample data | ✅ | 3 |
| Shehri ka report page (browser, English/Urdu, GPS, reference number) | ✅ | 4 |
| Report API: save pehle, dobara bhejne par dobara save nahi, ghalat form ruk jata hai | ✅ | 4 |
| AI Triage (Groq): type, severity, zakhmi, zaban, har ek ka confidence | ✅ | 5 |
| Trust score (rules, har point ki wajah) | ✅ | 5 |
| Gaariyon ka mashwara (qareeb pehle, ETA "approximate") | ✅ | 5 |
| AI band/fail ho to report bachi rehti hai (manual mode) | ✅ | 5 |
| Dashboard login, roles, account lock, idle logout | ✅ | 6 |
| Dashboard: incident queue aur review screen | ✅ | 7 |
| Gaari bhejna (Approve → Confirm, 3 click), lock, do dispatcher ek gaari, manual mode | ✅ | 8 |
| Driver ka safar (accept, decline, on scene … free) — **API se** (driver app abhi nahi) | ✅ | 9 |
| Dashboard par har gaari ka safar, Cancel, hospital badalna | ✅ | 9 |
| Audit log aur asli report ko koi badal nahi sakta | ✅ | 10 |
| Automatic tests (backend + web) | ✅ | 11 |
| Driver app (mobile), driver duty/GPS, driver ko alert, 60-s jawab timeout, live map, routes (OSRM), awaaz/SMS reports, duplicate detection, review queue, report edit, admin panel, analytics | ❌ **abhi nahi** | 12 (`501`) |

---

## Hissa 1 — Ek dafa ki tayyari

### 1.1 Zaroori cheezein
- **Docker** chal raha ho: `docker info` (error na aaye).
- **Node.js 22.12+** (web pages ke liye): `node -v` → `v22…` ya `v24…`.
- Project folder:
  ```bash
  cd /media/arjun-talreja/partition2/FYP_impl_material/FYP_Proeject/AMCEDS-FYP-Project
  ```

### 1.2 `.env` (sirf `.env` mein — `.env.example` mein asli password/key **kabhi nahi**)
| Setting | Kya ho |
|---|---|
| `POSTGRES_PASSWORD` | database ka password |
| `DATABASE_URL` | `postgresql+asyncpg://dispatch:<WAHI PASSWORD>@postgres:5432/dispatch` — andar **wahi** password jo `POSTGRES_PASSWORD` mein |
| `JWT_SECRET` | lamba random text |
| `JWT_EXPIRE_MINUTES` | `15` |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | `groq` / `openai/gpt-oss-120b` / aap ki Groq key |
| `SEED_ADMIN_PASSWORD`, `SEED_DISPATCHER_PASSWORD`, `SEED_DRIVER_PASSWORD` | test logins ke password (kam az kam 8 characters) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5174` |

### 1.3 Teen terminal
- **Terminal 1 — backend:** database, API aur AI worker. Yahan worker ka log chalta rehta hai.
- **Terminal 2 — web pages:** report page aur dashboard.
- **Terminal 3 — aap ke commands:** `curl`, database, tests.

### 1.4 Database kholna (Terminal 3)
```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```
`dispatch=#` prompt aayega. SQL yahan paste karein; bahar `\q`.

### 1.5 "Tayyari SQL" — gaari bhejne wale har test se pehle
Driver app abhi nahi bani, is liye drivers ko on-duty aur gaariyon ko free **SIMULATED SQL** se karte hain:
```sql
-- SIMULATED: purane test trips band, sab gaariyan free, drivers on duty, GPS abhi aayi
UPDATE assignments SET status = 'completed', completed_at = now() WHERE status IN ('approved', 'accepted');
UPDATE vehicles SET status = 'available', last_seen_at = now();
UPDATE users SET on_duty = true WHERE role = 'driver';
```
> ⏱ AI sirf us gaari ka **mashwara** deta hai jis ki GPS **60 second** ke andar aayi ho. Is liye ye SQL chalane ke **usi minute** mein report bhejein (Hissa 5.3, 8). Gaari bhejne (dispatch) ke liye purani GPS chal jati hai (sirf warning).

### 1.6 Login accounts (sample data)
| Username | Role | Gaari |
|---|---|---|
| `admin1` | admin | — |
| `dispatcher1`, `dispatcher2` | dispatcher | — |
| `driver01` | driver | SIM-AMB-01 |
| `driver02` | driver | SIM-FIRE-01 |
| `driver03` | driver | SIM-AMB-02 |
| `driver04` | driver | SIM-BKP-01 |
| `driver05` | driver | SIM-AMB-03 |
| `driver06` | driver | SIM-FIRE-02 |

Passwords `.env` wale `SEED_*_PASSWORD`. Hospitals: **SIMULATED General Hospital A** aur **B**.

> **Bilkul naye database se shuru karna (optional):** `python3 scripts/run_project.py stop`, phir `docker compose down -v` — ⚠️ ye **saari reports aur data mita deta hai**. Phir Hissa 2. Zaroori nahi; guide purane data ke saath bhi chalti hai.

---

## Hissa 2 — Project chalana

### 2.1 Backend (Terminal 1)
```bash
python3 scripts/run_project.py
```
**Sahi output** (beech mein Docker ki bohat si lines; ye zaroor dikhein):
```
==> Checking .env (values are not shown)
   .env looks OK.
==> Building and starting the database and the API
==> Waiting for the API at http://localhost:8000/health
   API is up: {"api":"ok","database":"ok"}
==> Checking the Groq API key and model
   Groq key works and model 'openai/gpt-oss-120b' is available
==> Creating / updating the database tables (migrations)
==> Loading SIMULATED sample data (size small; running it again adds nothing)
   The project is running.
==> Starting the AI worker (it reads new reports)
   The AI worker runs in the background. Its log follows; Ctrl+C stops only the log.
ai-worker-1  | ... INFO app.workers.ai_worker: ai-worker-...-1 starting with 2 slot(s)
```
- Pehli dafa `created: {'users': 9, 'vehicles': 6, 'hospitals': 2, ...}`; baad mein `already present: {...}` — dono sahi.
- **Ctrl+C sirf log band karta hai** — database, API aur worker chalte rehte hain.

Browser: http://localhost:8000/health → `{"api":"ok","database":"ok"}` ✅

### 2.2 Web pages (Terminal 2)
```bash
python3 scripts/run_project.py web
```
**Sahi output:**
```
==> Starting the web pages. Press Ctrl+C to stop them.
   - report page : http://localhost:5174
   - dashboard   : http://localhost:5173
```
⚠️ Band karne ke liye **Ctrl+C** — **Ctrl+Z nahi** (Ctrl+Z sirf rok deta hai aur port pakde rehta hai). Galti se Ctrl+Z ho jaye: usi terminal mein `fg`, phir Ctrl+C.

### 2.3 Kya chal raha hai
```bash
python3 scripts/run_project.py status
```
→ `ai-worker running`, `api running`, `postgres running`.

### 2.4 Masle aur hal
| Error / alamat | Matlab | Hal |
|---|---|---|
| `the user/password inside DATABASE_URL is not the same as POSTGRES_USER/POSTGRES_PASSWORD` | `.env` mein do alag password | `DATABASE_URL` mein wahi password likhein jo `POSTGRES_PASSWORD` mein |
| `the API was not healthy … database: down` | API database se nahi mil rahi | upar wala password; `docker compose ps` |
| `model '…' is NOT available on Groq` | model band ho gaya | script jo list dikhaye us mein se ek `LLM_MODEL` mein |
| `Groq says the API key is wrong or revoked (HTTP 401)` | key ghalat | Groq console se nayi key `.env` mein |
| `the web ports are already taken … PAUSED (Ctrl+Z …)` | purana `web` ruka hua hai | us terminal mein `fg` phir Ctrl+C, ya terminal band |
| `WARNING: the API is not running…` (web) | backend band hai | Terminal 1 mein 2.1 |
| `Docker is installed but not running` | Docker band | Docker start karein |
| Report `needs_check` + `ai_failed` har dafa | AI kaam nahi kar raha | Terminal 1 log; Groq key/model (`--no-seed` se dobara start) |

---

## Hissa 3 — Database aur sample data

Database kholein (1.4):
```sql
SELECT count(*) AS app_tables FROM pg_tables
 WHERE schemaname='public' AND tablename NOT IN ('spatial_ref_sys','alembic_version');
SELECT count(*) AS settings_rows FROM settings;
SELECT (SELECT count(*) FROM users) users, (SELECT count(*) FROM vehicles) vehicles, (SELECT count(*) FROM hospitals) hospitals;
SELECT plate_number, vehicle_type FROM vehicles ORDER BY 1;
```
**Sahi output:** `app_tables 15`, `settings_rows 35`, `users 9 | vehicles 6 | hospitals 2`; gaariyan `SIM-AMB-01/02/03` (ambulance), `SIM-BKP-01` (backup), `SIM-FIRE-01/02` (fire_truck). ✅

---

## Hissa 4 — Shehri report bhejta hai

### 4.1 Report page dekhein
Browser: **http://localhost:5174**
✅ Pass agar:
- Sab se upar laal dabbe mein **"☎ If life is in danger, also call 1122."**
- Peeli warning nahi (backend chal raha hai). Backend band karein to ~15 s mein "Cannot reach the server." — 1122 wala dabba phir bhi rehta hai.
- **"🎤 Record voice (coming soon)"** dabta nahi.
- Phone size par theek (Chrome F12 → phone icon → 360 px).

### 4.2 Apni report bhejein
1. "What happened?" → `SIMULATED: Clock Tower ke paas bus accident, 3 log zakhmi`
2. **Use my location** → Allow → `📍 Your location is added (accurate to about … m).` (Inkaar par: `Location permission was refused. Please type the place or a landmark below.` — report phir bhi jati hai.)
3. Optional: "Place or landmark" `near Clock Tower`, naam, phone `0300 1234567`.
4. **Send report**.

**Sahi output:** hari screen **"✔ Report saved"**, bara reference number (masalan **`INC-000012`**), "Your report is saved and is in the dispatcher's queue."

Database:
```sql
SELECT reference_no, channel, status, location_text, location_source, client_request_id
  FROM incidents ORDER BY incident_id DESC LIMIT 1;
```
→ wahi reference, `channel = web`, aap ka landmark, GPS di thi to `location_source = gps`. 5–10 s baad `status = triaged` (AI ne padh li).

### 4.3 Ghalat form (koi request nahi jati)
| Kya karein | Sahi nateeja |
|---|---|
| Khaali "What happened?" + Send | `Please describe what happened.`, cursor us box par |
| Phone `abc` | `Use digits only, for example 0300 1234567.`, box laal |
| 2000 se zyada characters | ginti laal `2001 / 2000`, `Too long: at most 2000 characters.` |

### 4.4 Network band → dobara bhejna (TC-04)
1. Form bharein → F12 → **Network** → **Offline** → **Send report** → `Your report was not sent: no connection. … it will not be sent twice.` (koi reference **nahi**).
2. **Online** → **Send report** dobara → "Report saved".
3. Database mein report sirf **ek dafa**:
   ```sql
   SELECT client_request_id, count(*) FROM incidents GROUP BY 1 HAVING count(*) > 1;
   ```
   → `(0 rows)` ✅

### 4.5 Database band (503)
Terminal 3: `docker compose stop postgres` → page par report bhejein → **`Your report was NOT saved. If life is in danger, call 1122 now.`**, koi reference nahi, likha hua text form mein mehfooz.
Phir `docker compose start postgres`, 10 s baad Send → "Report saved". ✅

### 4.6 Urdu
Upar **اردو** → poora page right-to-left, labels Urdu ("کیا ہوا ہے؟", "رپورٹ بھیجیں"), notice "اگر جان کو خطرہ ہو تو 1122 پر بھی کال کریں۔". Urdu report bhejein → "رپورٹ محفوظ ہو گئی". **English** se wapas.

### 4.7 Wahi kaam API se (terminal)
```bash
curl -s -w ' [HTTP %{http_code}]\n' -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: Clock Tower ke paas bus accident hua hai, 3 log zakhmi hain","lat":27.7052,"lon":68.8574,"client_request_id":"meri-report-001"}'
```
- Pehli dafa: `{"reference_no":"INC-0000xx","status":"new",...} [HTTP 201]`
- **Wahi** command dobara: **same** reference aur **`[HTTP 200]`** — dobara save nahi hui (TC-04).

Ghalat body → `[HTTP 422]`, `"code":"validation_error"`:
| Body | `msg` |
|---|---|
| `{"description":"   "}` | `String should have at least 1 character` |
| `{"description":"SIMULATED fire","lat":27.7}` | `lat and lon must both be given or both be left out` |
| `{"description":"SIMULATED fire","channel":"sms"}` | `this endpoint takes web and app reports; …` |
| `{"description":"SIMULATED fire","reporter_phone":"abc"}` | `String should match pattern …` |
| `{"description":"SIMULATED fire","status":"dispatched"}` | `Extra inputs are not permitted` |

---

## Hissa 5 — AI report ko padhta hai

### 5.1 Teen qisam ki reports
```bash
curl -s -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: مینارہ روڈ پر ایک دکان میں آگ لگ گئی ہے، دھواں بہت ہے","lat":27.7000,"lon":68.8600}'; echo
curl -s -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: kuch ho gaya hai jaldi aao"}'; echo
```
Terminal 1 ke log mein har report ke liye: `incident N: pipeline done; ran=['geocoding', 'triage', 'trust', 'allocation'] …`

### 5.2 Nateeja
```sql
SELECT reference_no, status, pipeline_state, incident_type, severity, victims_estimate, language, trust_tier, trust_score, review_reasons
  FROM incidents ORDER BY incident_id DESC LIMIT 3;
```
**Sahi output** (asal run):
```
 INC-000001 | triaged     | done | accident | high   | 3 | Roman Urdu | medium | 60 | {vehicle_shortage}
 INC-000002 | triaged     | done | fire     | medium |   | Urdu       | medium | 60 | {vehicle_shortage}
 INC-000003 | needs_check | done |          |        |   | Roman Urdu | low    | 35 | {location_unknown,low_trust_urgent,missing_info}
```
Kaise padhein:
- `pipeline_state = done` → AI ne kaam poora kiya; `pending` → abhi line mein.
- `triaged` → AI ne samjha; `needs_check` → **dispatcher khud dekhe**.
- Khaali value = AI ko pata nahi chala — **AI andaza nahi lagata**, jagah khud nahi banata.
- `review_reasons`: `missing_info` (type/jagah nahi pata, TC-07), `location_unknown`, `low_confidence` (60% se kam, TC-08 — report **fake nahi** banti), `vehicle_shortage` (us waqt gaari nahi thi), `ai_failed` (manual mode), `low_trust_urgent` (trust kam **lekin roki nahi**, safety rule 3).

✅ Accident → `accident`, aag → `fire`, vague → `needs_check` + `missing_info`. (AI severity kabhi `high` ki jagah `critical` de sakta hai — theek hai.)

### 5.3 Gaariyon ka mashwara
1. **Tayyari SQL** (1.5) chalayein.
2. Usi minute:
   ```bash
   curl -s -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
     -d '{"description":"SIMULATED: Military Road par truck aur car ki takkar, 5 log zakhmi, 2 behosh","lat":27.7100,"lon":68.8500}'; echo
   ```
3. 10 s baad:
   ```sql
   SELECT r.rank, v.plate_number, r.vehicle_type, r.distance_meters, r.eta_seconds, r.eta_is_approximate
     FROM recommendations r JOIN vehicles v USING (vehicle_id)
    WHERE r.incident_id = (SELECT max(incident_id) FROM incidents) AND r.is_current ORDER BY r.rank;
   SELECT count(*) AS assignments_open FROM assignments WHERE status IN ('approved','accepted');
   ```
**Sahi output** (asal run):
```
 1 | SIM-AMB-03 | ambulance |  802 |  72 | t
 2 | SIM-AMB-01 | ambulance |  903 |  81 | t
 3 | SIM-AMB-02 | ambulance | 2580 | 232 | t
 4 | SIM-BKP-01 | backup    | 4951 | 446 | t
 assignments_open = 0
```
✅ Qareeb pehle; `eta_is_approximate = t` (seedhi lakeer ka andaza); **mashwara gaari lock nahi karta** aur khud kuch nahi bhejta (assignments 0). `vehicle_shortage` aur khaali list → 60 s guzar gaye; 1.5 dobara.

### 5.4 Trust ki wajah
```sql
SELECT reference_no, trust_score, trust_tier, trust_signals FROM incidents ORDER BY incident_id DESC LIMIT 3;
```
→ har point ke saath wajah: `{"code": "real_details", "points": 10, "detail": "the message names a place, an event or people hurt"}`, vague par `-15`. 50 se shuru. ✅

### 5.5 AI band ho to report bachi rehti hai
1. `docker compose stop ai-worker`
2. Report bhejein (4.7) → **201** (AI band, phir bhi save).
3. `SELECT reference_no, status, pipeline_state FROM incidents ORDER BY incident_id DESC LIMIT 1;` → `new | pending` (line mein).
4. `docker compose up -d ai-worker` → kuch second baad `triaged | done`. ✅ Koi report zaya nahi.

### 5.6 AI fail ho (manual mode) — optional
```bash
docker compose stop ai-worker
docker compose run --rm -e LLM_MODEL=SIMULATED-broken-model ai-worker
```
Terminal 3 se report bhejein, 15 s baad → `needs_check | failed | medium | {ai_failed}` — report save, trust phir bhi bana. Ctrl+C se ghalat worker band, phir `docker compose up -d ai-worker`. ✅

### 5.7 Worker zinda hai
```sql
SELECT worker_id, last_seen_at::time(0), info FROM worker_heartbeats ORDER BY last_seen_at DESC LIMIT 1;
```
→ `"llm_ready": true`, `"llm_model": "openai/gpt-oss-120b"`, `"jobs_done": …`. (`stt_ready: false` theek — awaaz abhi nahi.)

---

## Hissa 6 — Dashboard login aur roles

Browser: **http://localhost:5173**

| Test | Kya karein | Sahi output |
|---|---|---|
| 6.1 Bina login | http://localhost:5173/queue kholein | khud `/login` par: "Sign in" |
| 6.2 Dispatcher | `dispatcher1` + password | `/queue`, "Signed in as SIMULATED Dispatcher One (Dispatcher)", "Incident queue" |
| 6.3 Ghalat role | dispatcher se `/admin` | "Not allowed — Your role may not open this page." + "Go to my start page" |
| 6.4 Admin | Sign out → `admin1` | `/admin`: "Administration is not built yet (task B1-A1-31)."; `/queue` → Not allowed |
| 6.5 Driver | `driver01` | "Drivers use the mobile app, not the dashboard. You have been signed out." |
| 6.6 Ghalat password | `dispatcher2` + ghalat | "Wrong username or password.", password box khaali |
| 6.7 Account lock (TC-32) | 5 dafa ghalat | "Too many wrong passwords. The account is locked; try again in 15 minute(s)." — sahi password bhi nahi chalta |
| 6.8 Sign out | **Sign out** | "You have signed out." |
| 6.9 Reload | login ke baad F5 | dobara login maangta hai (token sirf memory mein — mehfooz, sahi hai) |
| 6.10 Idle (optional, 30 min) | 28 min kuch na chhooein | peeli pati "…signed out in 2 minutes" + **Stay signed in**; 30 min par "You were signed out after 30 minutes without activity." |

Lock kholna (6.7 ke baad):
```sql
UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE username = 'dispatcher2';
```
Audit:
```sql
SELECT l.action, u.username, l.created_at::time(0) FROM audit_logs l LEFT JOIN users u USING (user_id)
 WHERE l.action LIKE 'auth.%' ORDER BY l.log_id DESC LIMIT 6;
```
→ `auth.login`, `auth.logout`, `auth.login_failed`, `auth.locked`. ✅

**API se roles** (http://localhost:8000/docs → **POST /auth/login** → token → upar **Authorize**):
| Request | Token | Sahi |
|---|---|---|
| GET /auth/me | koi nahi | `401` `unauthorized` |
| GET /auth/me | dispatcher | `200`, naam aur `"role":"dispatcher"` |
| GET /admin/users | dispatcher | `403` `forbidden` |
| GET /incidents | driver | `403` `forbidden` |
| POST /auth/logout, phir GET /auth/me | wahi purana | `204`, phir `401` `session_ended` |

---

## Hissa 7 — Dashboard par queue aur review

Pehle **Tayyari SQL** (1.5), phir usi minute 2–3 reports (accident GPS ke saath, Urdu aag, vague) — 4.2 ya 5.1 se.

### 7.1 Queue (`dispatcher1`)
**Sahi output** (asal run):
```
▲▲ Critical  Accident  INC-000001  Triaged     1 min ago  📍 GPS 27.7100, 68.8500  Trust: Medium (60)  ⚠ Not enough vehicles
?  Severity unknown  Type unknown  INC-000003  Needs check  📍 Location unknown  Trust: Low (35)
   ⚠ Location unknown  ⚠ Low trust — urgent, not held back  ⚠ More information needed
■  Medium  Fire  INC-000002  Triaged  📍 GPS 27.7000, 68.8600  Trust: Medium (60)
```
✅ Pass agar:
- Tarteeb **critical → high → severity maloom nahi → medium → low**; ek severity mein purani upar.
- Nayi report pehle **"⏳ AI is reading this report…"**, 5–10 s mein khud badal jati hai (reload nahi).
- Nayi **critical** par upar **"🔴 1 new critical report(s)"** aur laal card.
- `Updated hh:mm:ss` har 5 s badalta hai; doosre tab par refresh rukta hai, wapas aate hi chalta hai.

### 7.2 Review screen (card par click)
- **Report as received:** report bilkul waisi (Urdu right-to-left), reporter, "via Web", jagah.
- **What the AI understood** + "🤖 AI recommendation — dispatcher decides": `Type Accident — Type: 96%`, `Severity ▲▲ Critical — 85%`, `People hurt 7 — 80%`, `Language — 95%`, `Overall`. 60% se kam par **"Dispatcher must check"**.
- **Trust:** `Trust: Medium (60)`, "Every report starts at 50.", `+10 the message names a place, an event or people hurt`.
- **Why the dispatcher should look:** reasons saaf alfaaz mein.
- **Recommended vehicles:** `1 SIM-AMB-03 Ambulance 0.8 km 1 min ≈ Approximate` …
- `/incidents/99999` → "There is no incident with this number."; `admin1` se `/incidents/1` → Not allowed.

> Note: "5 log zakhmi, 2 behosh" ko AI ne **7** gina (confidence 80%). Isi liye confidence dikhaya jata hai — faisla dispatcher ka.

---

## Hissa 8 — Gaari bhejna (dispatch)

**Tayyari SQL** (1.5), phir usi minute ek nayi accident report.

### 8.1 Teen click (NFR-P14)
1. Queue mein nayi report par **click** (1).
2. "Recommended vehicles" mein **zaroori gaariyan pehle se ticked** (spare aur busy nahi). "Hospital (optional)" se **SIMULATED General Hospital A** chun sakte hain.
3. **Approve dispatch** (2) → dabba "Confirm dispatch": reference, severity, "Vehicles to send: SIM-AMB-03 — Ambulance", "Hospital: …".
4. **Confirm** (3).

**Sahi output:**
```
✔ Dispatched: SIM-AMB-03, SIM-BKP-01.
☎ The driver is not alerted automatically yet — inform the driver by radio or phone.
```
Neeche **Dispatched vehicles** card: `SIM-AMB-03  Ambulance  Waiting for the driver to accept`, "approved hh:mm by you · Hospital: …". Report ka status **Dispatched**.
Database:
```sql
SELECT i.reference_no, v.plate_number, v.status AS vehicle, a.status, u.username AS approved_by
  FROM assignments a JOIN incidents i USING (incident_id) JOIN vehicles v USING (vehicle_id) JOIN users u ON u.user_id = a.approved_by
 ORDER BY a.assignment_id DESC LIMIT 3;
SELECT details->'recommended' AS ai, details->'selected' AS chosen, details->'same_as_ai' AS same, details->'manual_mode' AS manual
  FROM audit_logs WHERE action = 'dispatch.approved' ORDER BY log_id DESC LIMIT 1;
```
→ gaari `assigned`, assignment `approved`, `dispatcher1`; audit mein AI ki list aur chuni hui (`same = true`). ✅

### 8.2 Kuch na bhejna
Approve → **Cancel** ya **Esc** → koi request nahi (assignments mein nayi row nahi). ✅

### 8.3 AI se alag gaari
Tick hatayein → **Other vehicles** → koi aur tick → Approve → **"Different from the AI suggestion."** + "Reason (optional)" → wajah → Confirm → audit `override_reason` aur `same_as_ai = false`. ✅

### 8.4 Do dispatcher, ek gaari (TC-22)
1. Do windows (ek private): `dispatcher1` aur `dispatcher2`, **ek hi nayi report**, dono **Approve dispatch** (dabba khula).
2. Pehli window **Confirm** → Dispatched.
3. Doosri **Confirm** → laal: **"Not sent: SIM-AMB-03 is already on another job."** + **"Use SIM-AMB-01 instead"**.
4. Us par click → dabbe mein gaari badal jati hai → Confirm → "Dispatched: SIM-AMB-01". ✅

Busy gaari list mein halki, checkbox band: "not available now: already on another job" (off-duty driver: "driver off duty").

### 8.5 Manual mode
Vague report (jagah nahi, AI mashwara nahi) → **"🛠 Manual dispatch — no AI recommendation."**, "Other vehicles" khud khuli, kuch ticked nahi → ek gaari tick → Approve → "Manual dispatch (no AI recommendation)." → Confirm → audit `manual_mode = true`. ✅

### 8.6 Fake report
```sql
UPDATE incidents SET status = 'fake' WHERE reference_no = 'INC-0000xx';
```
→ review screen: **"This report is fake: no vehicle can be sent."**, koi checkbox/button nahi. API se bhi `POST /incidents/{id}/dispatch` → `409 incident_not_dispatchable`. ✅

### 8.7 Dispatch ke inkaar API se (http://localhost:8000/docs, dispatcher token)
| Request | Sahi |
|---|---|
| `GET /api/v1/vehicles?incident_id=N` | har gaari: `can_dispatch`, `distance_meters`, `signal_lost`, `driver_on_duty` |
| `POST /incidents/N/dispatch` `{"vehicle_ids":[X]}` jab X busy | `409 vehicle_locked`, `details.next_best: [...]` |
| off-duty driver ki gaari (`UPDATE users SET on_duty=false WHERE username='driver06';`) | `409 vehicle_unavailable`, `reason: "driver_off_duty"` |
| `{"vehicle_ids": []}` ya `[5, 5]` | `422 validation_error` |
| bina token / driver / admin token | `401` / `403`, koi assignment nahi (TC-46) |

---

## Hissa 9 — Driver ka safar (aur dashboard par us ka haal)

Driver app abhi nahi bani — driver ke kaam **http://localhost:8000/docs** se. Dashboard ka review screen saath khula rakhein: **reload kiye baghair** har tabdeeli 5 s mein wahan dikhni chahiye.

Pehle 8.1 se ek gaari bhejein (masalan SIM-AMB-03 → driver **`driver05`**).

### 9.1 Driver ko apna kaam dikhe
`/docs` → login `driver05` → Authorize → **GET /api/v1/driver/assignments/current**
**Sahi (200)**, asal run: `{"assignment_id": 4, "reference_no": "INC-000005", "status": "approved", "incident_type": "accident", "patients": 2, "eta_seconds": 74, "eta_is_approximate": true, "hospital": {...}}`. Koi kaam nahi → **204**.

### 9.2 Poora safar (TC-29)
| Driver request (`/api/v1/driver/assignments/{id}/…`) | Sahi | Dashboard card |
|---|---|---|
| `status` `{"status":"picked_up"}` (accept se pehle) | **409** `invalid_transition` | koi tabdeeli nahi |
| `accept` | 200 `accepted` | **On the way** |
| `status` `{"status":"on_scene"}` | 200, `on_scene_at` | **On scene**; report **On scene** |
| `status` `{"status":"picked_up"}` | 200, `picked_up_at` | **Patient picked up** |
| `status` `{"status":"at_hospital"}` | 200, `at_hospital_at` | **At hospital** |
| `status` `{"status":"available"}` | 200 `completed` | **Trip completed — vehicle free** |

Har card par timeline: `Approved hh:mm  Accepted hh:mm  On scene hh:mm …`. Aakhri gaari khatam → report **Closed** (queue se hat jati hai; `GET /incidents?include_closed=true` mein). Driver ka `current` → **204**. Mareez ke baghair: `on_scene` ke baad seedha `available`. ✅

### 9.3 Driver jawab na de (yaad-dihani)
Nayi dispatch, driver kuch na kare → 1 min baad card par: **"⏱ No answer from the driver for 1 min — call the driver, or cancel and send another."** (Sirf yaad-dihani; asli timeout abhi nahi bana.)

### 9.4 "Cannot go" (decline, TC-27)
Driver: `decline` `{"reason":"too_far"}` → 200 `declined`. (Wajahein sirf: `vehicle_problem`, `crew_unavailable`, `already_busy`, `too_far`, `other`; koi aur → 422; accept ke baad decline → 409.)
Dashboard: card **"Declined: too far"**; agar koi aur gaari nahi ja rahi to report **Needs check** + **"⚠ A vehicle could not go — send another"**, aur panel dobara zaroori gaariyan tick kar deta hai. ✅

### 9.5 Hospital badalna (dashboard)
Card par **Change hospital** → **SIMULATED General Hospital B** → **Save** → "✔ Hospital changed to SIMULATED General Hospital B — inform the driver." Driver `current` → `hospital.name = "SIMULATED General Hospital B"`. (Wahi hospital ho to Save band.) ✅

### 9.6 Cancel (dashboard)
Card par **Cancel vehicle** → "Cancel SIM-AMB-01?" → **Keep it** (kuch nahi) → dobara → wajah → **Cancel this vehicle** → "✔ SIM-AMB-01 cancelled — inform the driver.", card **Cancelled**. Akeli gaari thi to report **Needs check** + "⚠ Vehicle cancelled — send another". Band (completed) trip par button nahi. ✅

### 9.7 Hifazat
| Kya | Sahi |
|---|---|
| Doosre driver ke token se kisi aur ki assignment accept/decline/status | **403** (TC-48) |
| Off-duty driver accept | **409** `driver_off_duty` |
| Driver token se cancel ya hospital change | **403** |

Audit:
```sql
SELECT action, details->>'step' AS step, details->>'reason' AS reason, created_at::time(0)
  FROM audit_logs WHERE action LIKE 'assignment.%' OR action = 'vehicle.unlocked' ORDER BY log_id DESC LIMIT 10;
```
→ `assignment.accepted`, `assignment.status_changed`, `assignment.hospital_changed`, `assignment.cancelled` (wajah ke saath), `vehicle.unlocked`. ✅

---

## Hissa 10 — Audit aur asli report koi nahi badal sakta

Ek ek kar ke chalayein (in ka **ERROR** dena hi kamyabi hai):
```sql
UPDATE audit_logs SET action = 'hacked' WHERE log_id = (SELECT max(log_id) FROM audit_logs);
DELETE FROM audit_logs WHERE log_id = (SELECT max(log_id) FROM audit_logs);
UPDATE incidents SET original_text = 'changed' WHERE incident_id = (SELECT max(incident_id) FROM incidents);
```
**Sahi output:**
```
ERROR:  audit_logs rows cannot be changed or deleted (NFR-C10)
ERROR:  audit_logs rows cannot be changed or deleted (NFR-C10)
ERROR:  incidents.original_text cannot be changed once saved
```
Ek report ka poora record:
```sql
SELECT action, created_at::time(0) FROM audit_logs WHERE incident_id = (SELECT max(incident_id) FROM incidents) ORDER BY log_id;
```
→ `report.received`, `ai.geocode`, `ai.triage`, `ai.trust`, `ai.allocation` (aur dispatch hui ho to `dispatch.approved`, `vehicle.locked`, `assignment.*`). ✅

---

## Hissa 11 — Automatic tests

Terminal 3:
```bash
python3 scripts/run_project.py test        # backend
python3 scripts/run_project.py test-web    # web: tests, typecheck, build
```
**Sahi output:**
```
967 passed, 3 skipped in 74.73s (0:01:14)
   RESULT: all tests passed
```
```
   tests     : passed
   typecheck : passed
   build     : passed
```
(Web mein upar kahin `Tests  164 passed (164)`.)
- Backend ke 3 skip normal hain (wo docs folder dekhte hain jo container mein nahi). Poore repo ke saath:
  ```bash
  docker compose run --rm -v "$PWD":/repo -w /repo/backend api pytest -q -rs
  ```
  → **970 passed, 0 skipped**.
- Tests aap ka data **nahi** chhooti (alag `dispatch_test` database).

✅ Pass: `0 failed`.

---

## Hissa 12 — Jo abhi nahi bana (`501` dena sahi hai)

Ye endpoints contract mein hain lekin bane nahi. Inhein kholne par **501** aur task number aana **sahi** hai (koi jhoota "success" nahi):

| Kya | Endpoints | Task |
|---|---|---|
| Awaaz ki report | `POST /reports/voice`, `GET /incidents/{id}/audio` | B1-A1-17 |
| Shehri se tasdeeq | `POST /reports/{ref}/confirmation`, `POST /incidents/{id}/confirmation-requests` | B1-A1-24 |
| SMS/voice simulator | `POST /intake/sms`, `POST /intake/voice` | B4-01, B4-02 |
| Report edit | `PATCH /incidents/{id}` | B1-A1-21 |
| Duplicate faisle | `POST /duplicate-candidates/{id}/confirm`, `/reject` | B1-A1-22 |
| Review queue (Real/Fake) | `GET /review-queue`, `POST /incidents/{id}/review-decision` | B1-A1-23 |
| Driver duty aur GPS, live fleet | `POST /driver/duty/start`, `/duty/end`, `POST /driver/locations`, `GET /fleet/live` | B1-A1-27 |
| Road route | `GET /routing/route` | B1-A2-15 |
| Admin panel | `/admin/users`, `/admin/vehicles`, `/admin/hospitals`, `/admin/settings`, `/admin/audit-logs` | B1-A1-31 |
| Reports aur analytics | `/analytics/incidents`, `/analytics/performance`, `/analytics/export` | B1-A1-32 |

Misaal (driver token): **POST /api/v1/driver/duty/start** → `501` `{"code":"not_implemented","message":"… (task B1-A1-27).","details":{"task":"B1-A1-27"}}`.

Aur abhi nahi: driver ko alert (B1-A1-30), 60-s jawab timeout (B1-A1-28), WebSocket live updates (B1-A1-29; abhi 5-s refresh), live map, mobile app.

---

## Hissa 13 — Band karna aur saaf karna

- Web pages: Terminal 2 mein **Ctrl+C** → `Web pages stopped.`
- Sab kuch (data mehfooz): `python3 scripts/run_project.py stop`
- Sirf AI worker: `docker compose stop ai-worker` (wapas: `docker compose up -d ai-worker`)
- Test ke baad gaariyan free: **Tayyari SQL** (1.5).
- ⚠️ `docker compose down -v` **sab data mita deta hai** — sirf jab bilkul naye se shuru karna ho.

---

## Aakhri checklist — tick karte jayein

| # | Check | Sahi nateeja | ✔ |
|---|---|---|---|
| 1 | Backend start | `API is up … ok`, Groq model available, worker `starting with 2 slot(s)` | ☐ |
| 2 | Web start | report page 5174, dashboard 5173 | ☐ |
| 3 | Database | 15 tables, 35 settings, 9 users, 6 gaariyan, 2 hospitals | ☐ |
| 4 | Report page | 1122 notice, voice button band | ☐ |
| 5 | Browser se report | "Report saved" + `INC-…`, `channel = web` | ☐ |
| 6 | GPS / inkaar | location added / "permission was refused", report phir bhi jati hai | ☐ |
| 7 | Ghalat form | request nahi jati, saaf message | ☐ |
| 8 | Offline → online | pehle "not sent", phir saved; database mein ek dafa | ☐ |
| 9 | Database band | "NOT saved … call 1122", koi reference nahi | ☐ |
| 10 | Urdu | RTL, Urdu labels aur notice | ☐ |
| 11 | API resend | same reference, `HTTP 200` | ☐ |
| 12 | API ghalat body | `422 validation_error` | ☐ |
| 13 | AI: accident / aag / vague | `accident` / `fire` / `needs_check` + `missing_info` | ☐ |
| 14 | Mashwara | qareeb pehle, `≈ approximate`, assignments 0 | ☐ |
| 15 | Trust | har point ki wajah | ☐ |
| 16 | Worker band → report | 201, `pending`, worker chalne par `done` | ☐ |
| 17 | AI fail | `needs_check`, `failed`, `{ai_failed}` | ☐ |
| 18 | Heartbeat | `llm_ready: true` | ☐ |
| 19 | Dashboard bina login | `/login` | ☐ |
| 20 | Dispatcher / admin / driver login | `/queue` / `/admin` / "Drivers use the mobile app" | ☐ |
| 21 | Ghalat role | "Not allowed" | ☐ |
| 22 | Ghalat password / lock | saaf message, 5 ke baad locked | ☐ |
| 23 | Sign out / reload | "You have signed out." / dobara login | ☐ |
| 24 | API roles | 401 / 403 / `session_ended` | ☐ |
| 25 | Queue tarteeb | critical → high → unknown → medium → low | ☐ |
| 26 | Queue refresh | nayi report khud aati hai, "AI is reading" phir nateeja | ☐ |
| 27 | Nayi critical | "🔴 new critical" aur laal card | ☐ |
| 28 | Review: AI | har value ke saath confidence, 60% se kam par "Dispatcher must check" | ☐ |
| 29 | Review: trust, reasons, gaariyan | wajahein, plate, km, minute, "≈ Approximate" | ☐ |
| 30 | 3 click dispatch | "Dispatched …" + "inform the driver", status Dispatched | ☐ |
| 31 | Cancel / Esc (approve dabba) | kuch nahi jata | ☐ |
| 32 | AI se alag gaari | "Different from the AI suggestion", wajah audit mein | ☐ |
| 33 | Do dispatcher ek gaari | "already on another job" + "Use … instead" → Dispatched | ☐ |
| 34 | Manual mode | label, list khuli, audit `manual_mode` | ☐ |
| 35 | Fake report | koi control nahi, API `409` | ☐ |
| 36 | Dispatch API inkaar | `vehicle_locked` / `vehicle_unavailable` / `422` / `401-403` | ☐ |
| 37 | Driver current | 200 apna kaam / 204 | ☐ |
| 38 | Poora safar | har qadam ka waqt, card ka haal badalta hai, gaari free, report Closed | ☐ |
| 39 | Ghalat tarteeb | accept se pehle `picked_up` → 409 | ☐ |
| 40 | Jawab na mile | 1 min baad "No answer from the driver" | ☐ |
| 41 | Decline | "Declined: too far", report Needs check + "could not go" | ☐ |
| 42 | Hospital badalna | "Hospital changed … inform the driver", driver ko naya hospital | ☐ |
| 43 | Cancel gaari | tasdeeq, "cancelled — inform the driver", haal Cancelled | ☐ |
| 44 | Doosre driver ki assignment | 403 | ☐ |
| 45 | Audit / original text badalna | teeno `ERROR` | ☐ |
| 46 | Automatic tests | backend aur web `0 failed` | ☐ |
| 47 | Na bane endpoints | `501` + task number | ☐ |
