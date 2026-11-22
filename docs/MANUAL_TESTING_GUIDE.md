# AMCEDS — Haath se testing ki guide (step by step)

Ye guide aap ko batati hai ke **ab tak jo kuch bana hai** usay apne data ke saath kaise check karein, aur har step par **kya output aana chahiye**. Agar aap ka output neeche wale "Sahi output" jaisa hai, to wo hissa sahi chal raha hai.

> Har output **2026-11-22** ko is project par asal mein chala kar likha gaya hai. Aap ke reference number, time aur ID thode alag ho sakte hain; baaqi shakal wahi honi chahiye.
>
> **Sab data SIMULATED hai.** Apni reports mein `SIMULATED:` likhna acchi aadat hai, taake koi isay asli emergency na samjhe.

---

## Kya bana hai aur kya abhi nahi bana

| Hissa | Haal | Is guide ka step |
|---|---|---|
| Project start karne wala script | ✅ bana hai | Step 1 |
| Database (15 tables, 35 settings, sample data) | ✅ bana hai | Step 2 |
| Web/app se report bhejna (reference number milna) | ✅ bana hai | Step 3 |
| Same report dobara bhejne par dobara save na hona (TC-04) | ✅ bana hai | Step 3.2 |
| Ghalat form ko rokna (validation) | ✅ bana hai | Step 3.3 |
| AI Triage (type, severity, victims, language) — Groq | ✅ bana hai | Step 4 |
| Trust score (rules wala, AI nahi) | ✅ bana hai | Step 4.3 |
| Gaariyon ka mashwara (Resource Allocation) | ✅ bana hai | Step 5 |
| AI fail ho to report zaya na ho (manual mode) | ✅ bana hai | Step 6 |
| Login, token, logout, roles (admin/dispatcher/driver) | ✅ bana hai | Step 7 |
| 5 ghalat password par account lock (TC-32) | ✅ bana hai | Step 7.4 |
| Audit log ko koi badal/mita nahi sakta | ✅ bana hai | Step 8 |
| Automatic tests (906 backend + 130 web) | ✅ bana hai | Step 9 |
| Browser wala report page (English/Urdu, GPS, reference number) | ✅ bana hai | Step 12 |
| Dashboard login, roles, idle logout | ✅ bana hai | Step 13 |
| Dashboard par incident queue aur review (AI ke nateeje, gaariyon ke plates) | ✅ bana hai | Step 14 |
| Dispatch approval, incident edit, driver duty, admin pages, voice/SMS, duplicate detection, map/routes, mobile app | ❌ **abhi nahi bana** | Step 10 (ye `501` dete hain) |

---

## Step 0 — Ek dafa ki tayyari

1. Docker chal raha ho (`docker info` chalayein, error na aaye).
2. Project folder mein jayein:
   ```bash
   cd /media/arjun-talreja/partition2/FYP_impl_material/FYP_Proeject/AMCEDS-FYP-Project
   ```
3. `.env` mein ye sab bhare hon (khaali na hon):
   - `POSTGRES_PASSWORD` aur `DATABASE_URL` ke andar **wahi** password
   - `JWT_SECRET`, `JWT_EXPIRE_MINUTES=15`
   - `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b`, `LLM_API_KEY=...`
   - `SEED_ADMIN_PASSWORD`, `SEED_DISPATCHER_PASSWORD`, `SEED_DRIVER_PASSWORD` (kam az kam 8 characters)

Is guide mein **do terminal** use honge:
- **Terminal 1:** project + AI worker chalega (isay khula rehne dein).
- **Terminal 2:** aap tests chalayenge.

**Database kholne ka tareeqa** (Step 2, 4, 5, 6, 8 mein kaam aayega). Terminal 2 mein:
```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```
Ab `dispatch=#` jaisa prompt aayega. Yahan SQL paste karein. Bahar nikalne ke liye `\q` likhein.

---

## Step 1 — Project start karein

**Terminal 1** mein:
```bash
python3 scripts/run_project.py
```

**Sahi output** (beech mein Docker ki bohat si lines aayengi; ye wali zaroor dikhni chahiye):
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
created: {'users': 9, 'vehicles': 6, 'hospitals': 2, 'driver_links': 6}
   The project is running.
==> Starting the AI worker (it reads new reports). Press Ctrl+C to stop the worker.
... INFO app.workers.ai_worker: ai-worker-...-1 starting with 2 slot(s)
```
- Pehli dafa `created: {'users': 9, ...}` aayega. Dobara chalane par `created: {'users': 0, ...}` aur `already present: {'users': 9, 'vehicles': 6, 'hospitals': 2}` aayega — ye bhi **sahi** hai (sample data dobara nahi daalta).
- `WARNING: ... is empty` aaye to `.env` mein wo cheez bharein.

**Agar ye error aaye:**

| Error | Matlab | Hal |
|---|---|---|
| `model '...' is NOT available on Groq` | Groq ne wo model band kar diya | Script jo list dikhaye us mein se ek model `LLM_MODEL` mein likhein |
| `Groq says the API key is wrong or revoked (HTTP 401)` | Key ghalat/purani | Groq console se nayi key `.env` mein |
| `the user/password inside DATABASE_URL is not the same as ...` | Do jagah alag password | `DATABASE_URL` mein wahi password likhein jo `POSTGRES_PASSWORD` mein hai |
| `the API was not healthy ... database: down` | API database se connect nahi ho rahi | Upar wala password check karein |
| `Docker is installed but not running` | Docker band hai | Docker start karein |

**Browser check:** http://localhost:8000/health kholein →
```json
{"api":"ok","database":"ok"}
```
✅ Pass: dono `ok`.

---

## Step 2 — Database aur sample data check karein

Terminal 2 mein database kholein (Step 0 wala command) aur ye paste karein:

```sql
SELECT count(*) AS app_tables FROM pg_tables
 WHERE schemaname='public' AND tablename NOT IN ('spatial_ref_sys','alembic_version');
SELECT count(*) AS settings_rows FROM settings;
SELECT (SELECT count(*) FROM users) users, (SELECT count(*) FROM vehicles) vehicles,
       (SELECT count(*) FROM hospitals) hospitals;
SELECT username, role, full_name FROM users ORDER BY user_id;
SELECT plate_number, vehicle_type, status FROM vehicles ORDER BY 1;
```

**Sahi output:**
```
 app_tables
------------
         15

 settings_rows
---------------
            35

 users | vehicles | hospitals
-------+----------+-----------
     9 |        6 |         2
```
Users: `admin1` (admin), `dispatcher1`, `dispatcher2` (dispatcher), `driver01` … `driver06` (driver) — sab ke naam mein `SIMULATED`.
Vehicles: `SIM-AMB-01/02/03` (ambulance), `SIM-FIRE-01/02` (fire_truck), `SIM-BKP-01` (backup), sab `available`.

✅ Pass: 15 tables, 35 settings, 9 users, 6 vehicles, 2 hospitals.

---

## Step 3 — Report bhejna (citizen ki taraf se)

Do tareeqe hain. **Aasaan tareeqa:** browser mein http://localhost:8000/docs kholein → **POST /api/v1/reports** → **Try it out** → body mein JSON daalein → **Execute**.
**Terminal tareeqa:** neeche wale `curl` commands Terminal 2 mein chalayein.

### 3.1 Sahi report (apna data daalein)

```bash
curl -s -w ' [HTTP %{http_code}]\n' -X POST localhost:8000/api/v1/reports \
  -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: Clock Tower ke paas bus accident hua hai, 3 log zakhmi hain, khoon beh raha hai",
       "lat":27.7052,"lon":68.8574,
       "reporter_name":"SIMULATED Ali","reporter_phone":"0300 1234567",
       "client_request_id":"meri-report-001"}'
```
Aap `description`, `lat/lon` (Sukkur ke aas paas: lat 27.68–27.72, lon 68.84–68.90), naam aur phone apni marzi se badal sakte hain.

**Sahi output:**
```
{"reference_no":"INC-000001","status":"new","received_at":"2026-11-22T08:32:38.435545Z"} [HTTP 201]
```
✅ Pass: `HTTP 201` aur `INC-` + 6 digit wala reference number. (Report **pehle save** hoti hai, AI baad mein — safety rule 1.)

### 3.2 Wahi report dobara bhejein (TC-04)

Bilkul wahi command dobara chalayein (same `client_request_id`).

**Sahi output:**
```
{"reference_no":"INC-000001","status":"new","received_at":"2026-11-22T08:32:38.435545Z"} [HTTP 200]
```
✅ Pass: **same** reference number aur `HTTP 200` (201 nahi) — matlab report dobara save **nahi** hui. `client_request_id` badal dein to nayi report banegi.

### 3.3 Ghalat form — system ko rokna chahiye

Har ek ka jawab `HTTP 422` aur `"code":"validation_error"` hona chahiye:

| Aap kya bhejte hain (`-d '...'`) | Sahi output ka `msg` |
|---|---|
| `{"description":"   "}` (khaali) | `String should have at least 1 character` |
| `{"description":"SIMULATED fire","lat":27.7}` (sirf lat) | `lat and lon must both be given or both be left out` |
| `{"description":"SIMULATED fire","channel":"sms"}` | `this endpoint takes web and app reports; SMS and voice have their own endpoints` |
| `{"description":"SIMULATED fire","reporter_phone":"abc"}` | `String should match pattern ...` |
| `{"description":"SIMULATED fire","status":"dispatched"}` (faltu field) | `Extra inputs are not permitted` |

Misaal:
```bash
curl -s -w ' [HTTP %{http_code}]\n' -X POST localhost:8000/api/v1/reports \
  -H 'Content-Type: application/json' -d '{"description":"   "}'
```
```
{"code":"validation_error","message":"The request is not valid.","details":[{"loc":["body","description"],"msg":"String should have at least 1 character","type":"string_too_short"}]} [HTTP 422]
```
✅ Pass: paanchon `422` dein aur koi reference number na milay.

---

## Step 4 — AI ne report ko kaise samjha (Triage + Trust)

AI worker (Terminal 1) har nayi report ko 2–5 second mein padhta hai. Terminal 1 mein aisi line aayegi:
```
INFO app.agents.orchestrator: incident 1: pipeline done; ran=['geocoding', 'triage', 'trust', 'allocation'] ...
```

### 4.1 Teen qisam ki reports bhejein

```bash
# Urdu script — aag
curl -s -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: مینارہ روڈ پر ایک دکان میں آگ لگ گئی ہے، دھواں بہت ہے","lat":27.7000,"lon":68.8600}'; echo
# Ghair-wazeh (vague) — na type pata, na jagah
curl -s -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: kuch ho gaya hai jaldi aao"}'; echo
```
Apni marzi ki reports bhi bhejein: English, Urdu, Roman Urdu, Sindhi — aag, accident, doobna, medical, etc.

### 4.2 Nateeja dekhein

Database kholein aur:
```sql
SELECT reference_no, status, pipeline_state, incident_type, severity, victims_estimate,
       language, trust_tier, trust_score, review_reasons
  FROM incidents ORDER BY incident_id;
```

**Sahi output** (asal run):
```
 reference_no |   status    | pipeline_state | incident_type | severity | victims_estimate |  language  | trust_tier | trust_score |         review_reasons
--------------+-------------+----------------+---------------+----------+------------------+------------+------------+-------------+-----------------------------------------------
 INC-000001   | triaged     | done           | accident      | high     |                3 | Roman Urdu | medium     |          60 | {vehicle_shortage}
 INC-000002   | triaged     | done           | fire          | medium   |                  | Urdu       | medium     |          60 | {vehicle_shortage}
 INC-000003   | needs_check | done           |               |          |                  | Roman Urdu | low        |          35 | {location_unknown,low_trust_urgent,missing_info}
```

Isay kaise padhein:
- `pipeline_state = done` → AI ne kaam poora kiya. `pending` → abhi line mein hai (thoda intezar karein).
- `status = triaged` → AI ne samajh liya. `needs_check` → **dispatcher khud dekhe** (insaan ka faisla).
- `incident_type`, `severity`, `victims_estimate`, `language` → AI ne report se nikale. Khaali = AI ko pata nahi chala (AI **kabhi andaza nahi lagata**, jagah khud nahi banata).
- `review_reasons`:
  - `missing_info` → type ya jagah nahi pata (TC-07)
  - `location_unknown` → na GPS, na jagah ka naam
  - `low_confidence` → AI ko yaqeen 60% se kam (TC-08). Ye report ko **fake nahi** banata.
  - `vehicle_shortage` → us waqt koi gaari available nahi thi (Step 5 dekhein)
  - `ai_failed` → AI fail hua, manual mode (Step 6)
  - `low_trust_urgent` → trust kam hai **lekin** report roki nahi gayi (safety rule 3)

✅ Pass: accident → `accident`, aag → `fire`, vague → `needs_check` + `missing_info`. Urdu script par `Urdu`, Roman Urdu par `Roman Urdu`.

> AI kabhi kabhi severity thodi alag de sakta hai (masalan `high` ki jagah `critical`). Ye theek hai; important ye hai ke type aur samajh sahi ho, aur jo pata na ho wo khaali rahe.

### 4.3 Trust score ki wajah dekhein

```sql
SELECT reference_no, trust_score, trust_tier, trust_signals FROM incidents ORDER BY incident_id;
```
**Sahi output** (misaal):
```
 INC-000003 | 35 | low    | [{"code": "vague", "detail": "the message is vague or joking", "points": -15}]
 INC-000004 | 60 | medium | [{"code": "real_details", "detail": "the message names a place, an event or people hurt", "points": 10}]
```
✅ Pass: har point ke saath wajah (`detail`) likhi hai. 50 se shuru hota hai; asli details par +10, vague par −15.

---

## Step 5 — Gaariyon ka mashwara (Resource Allocation)

System sirf us gaari ko suggest karta hai jiska **driver on-duty ho** aur jiski **GPS pichle 60 second** mein aayi ho. Driver app abhi nahi bani, is liye ye haath se SIMULATED SQL se karna padega.

### 5.1 Drivers ko on-duty karein (SIMULATED)

Database mein:
```sql
-- SIMULATED: sab drivers on duty, GPS abhi aayi
UPDATE users SET on_duty = true WHERE role = 'driver';
UPDATE vehicles SET last_seen_at = now();
```
**Sahi output:** `UPDATE 6` do dafa.

> ⏱ Ye sirf **60 second** tak chalta hai (setting `signal_lost_s`). Report usi minute mein bhejein. Dobara test karna ho to `UPDATE vehicles SET last_seen_at = now();` phir se chalayein.

### 5.2 Fauran ek report bhejein

```bash
curl -s -w ' [HTTP %{http_code}]\n' -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
  -d '{"description":"SIMULATED: Military Road par truck aur car ki takkar, 5 log zakhmi, 2 behosh","lat":27.7100,"lon":68.8500}'
```

### 5.3 Mashwara dekhein (5 second baad)

```sql
SELECT reference_no, status, incident_type, severity, victims_estimate, review_reasons
  FROM incidents ORDER BY incident_id DESC LIMIT 1;

SELECT r.rank, v.plate_number, r.vehicle_type, r.distance_meters, r.eta_seconds, r.eta_is_approximate
  FROM recommendations r JOIN vehicles v USING (vehicle_id)
 WHERE r.incident_id = (SELECT max(incident_id) FROM incidents) ORDER BY r.rank;

SELECT plate_number, status FROM vehicles ORDER BY 1;
```

**Sahi output** (asal run):
```
 reference_no | status  | incident_type | severity | victims_estimate | review_reasons
--------------+---------+---------------+----------+------------------+----------------
 INC-000004   | triaged | accident      | critical |                5 | {}

 rank | plate_number | vehicle_type | distance_meters | eta_seconds | eta_is_approximate
------+--------------+--------------+-----------------+-------------+--------------------
    1 | SIM-AMB-03   | ambulance    |             802 |          72 | t
    2 | SIM-AMB-01   | ambulance    |             903 |          81 | t
    3 | SIM-AMB-02   | ambulance    |            2580 |         232 | t
    4 | SIM-BKP-01   | backup       |             4951 |         446 | t

 plate_number |  status
--------------+-----------
 SIM-AMB-01   | available     (sab 6 abhi bhi available)
```
✅ Pass:
- Sab se **qareeb** gaari rank 1 par.
- `eta_is_approximate = t` → seedhi line wala andaza, "approximate" label (safety rule 7; asal road route abhi nahi bana).
- Gaariyan abhi bhi `available` — **mashwara gaari ko lock nahi karta** (safety rule 6). Lock sirf dispatcher ki approval par hoga (abhi nahi bana).
- `assignments` table khaali rehti hai: `SELECT count(*) FROM assignments;` → `0` (koi gaari khud-ba-khud nahi bheji gayi — safety rule 2).

Agar `review_reasons = {vehicle_shortage}` aaye aur mashwara khaali ho → 60 second guzar gaye. 5.1 dobara karein.

---

## Step 6 — AI band ho ya fail ho, report phir bhi bachi rahe

### 6.1 Worker band karke report bhejein

1. Terminal 1 mein **Ctrl+C** dabayein. Sahi output:
   ```
      Stopping the AI worker (it finishes the report it is working on)...
      AI worker stopped. The database and API are still running.
   ```
2. Terminal 2 se report bhejein:
   ```bash
   curl -s -w ' [HTTP %{http_code}]\n' -X POST localhost:8000/api/v1/reports -H 'Content-Type: application/json' \
     -d '{"description":"SIMULATED: Barrage Road par ghar mein aag lagi hai, 2 bachay andar hain","lat":27.6900,"lon":68.8650}'
   ```
   **Sahi output:** `{"reference_no":"INC-000005","status":"new",...} [HTTP 201]` — AI band hai phir bhi report save hui.
3. Database mein: `SELECT reference_no, status, pipeline_state FROM incidents ORDER BY incident_id DESC LIMIT 1;`
   ```
    INC-000005   | new    | pending
   ```
   Report line mein intezar kar rahi hai.
4. Terminal 1 mein worker dobara chalayein (sirf worker, baaqi sab chal raha hai):
   ```bash
   python3 scripts/run_project.py --no-seed
   ```
   Kuch second baad wahi query → `triaged | done`. ✅ Pass: koi report zaya nahi hui.

### 6.2 AI fail ho jaye (manual mode) — optional

Terminal 1 mein worker band karein (Ctrl+C), phir jaan-boojh kar ghalat model se chalayein:
```bash
docker compose run --rm --name amceds-ai-worker -e LLM_MODEL=SIMULATED-broken-model api python -m app.workers.ai_worker
```
Terminal 2 se ek report bhejein, 15 second baad:
```sql
SELECT reference_no, status, pipeline_state, trust_tier, review_reasons FROM incidents ORDER BY incident_id DESC LIMIT 1;
```
**Sahi output:**
```
 INC-000006   | needs_check | failed         | medium     | {ai_failed}
```
✅ Pass: report save hai, `needs_check` (dispatcher khud dekhe), trust phir bhi calculate hua. Ctrl+C se ye worker band karein aur `python3 scripts/run_project.py --no-seed` se sahi worker wapas chalayein.

---

## Step 7 — Login, token, roles

Browser mein http://localhost:8000/docs kholein.

### 7.1 Login (dispatcher)

**POST /api/v1/auth/login** → Try it out → body:
```json
{"username": "dispatcher1", "password": "<aap ka SEED_DISPATCHER_PASSWORD>"}
```
**Sahi output (200):**
```json
{"access_token":"eyJhbGciOiJI…","token_type":"bearer","expires_in":900,"refresh_token":"eyJhbGciOiJI…"}
```
`expires_in: 900` = 15 minute. `access_token` copy karein.

### 7.2 "Main kaun hoon"

Upar **Authorize** 🔒 button → token paste → Authorize. Phir **GET /api/v1/auth/me** → Execute.
**Sahi output (200):**
```json
{"user_id":2,"full_name":"SIMULATED Dispatcher One","username":"dispatcher1","role":"dispatcher","phone":null,"on_duty":false}
```
Bina Authorize kiye → `401` `{"code":"unauthorized","message":"Not signed in."}`.

### 7.3 Roles ki pabandi

Dispatcher ke token ke saath **GET /api/v1/admin/users** → **403**:
```json
{"code":"forbidden","message":"Your role may not do this.","details":null}
```
`driver01` se login karke (`SEED_DRIVER_PASSWORD`) **GET /api/v1/incidents** → **403** `forbidden`.
`admin1` se login karke **GET /api/v1/admin/users** → **501** `not_implemented` (role ijazat deta hai, page abhi bana nahi).

✅ Pass: har role sirf apni cheezein khol sakta hai.

### 7.4 Ghalat password — account lock (TC-32)

**POST /auth/login** par `dispatcher2` aur ghalat password `wrongpass1` **5 dafa** bhejein:
- Dafa 1–4: **401** `{"code":"invalid_credentials","message":"Invalid username or password."}`
- Dafa 5 aur us ke baad: **401** `{"code":"account_locked","message":"Too many wrong passwords. The account is locked; try again in 15 minute(s)."}`
- Ab **sahi** password bhi → `account_locked`.

✅ Pass. 15 minute intezar na karna ho to database mein unlock karein:
```sql
UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE username = 'dispatcher2';
```

### 7.5 Refresh aur logout

- **POST /auth/refresh** body `{"refresh_token":"<login wala refresh_token>"}` → **200**, naye tokens.
- **POST /auth/logout** (Authorize ke saath, koi body nahi) → **204** (khaali jawab).
- Us ke baad wahi purana token **GET /auth/me** par → **401** `{"code":"session_ended","message":"Your session has ended. Please sign in again."}`

✅ Pass: logout ke baad purana token kaam nahi karta.

---

## Step 8 — Audit log aur asli report ko koi badal nahi sakta

### 8.1 Har AI qadam record hota hai

```sql
SELECT action, created_at::time(0) AS at FROM audit_logs WHERE incident_id = 4 ORDER BY log_id;
```
**Sahi output:**
```
     action      |    at
-----------------+----------
 report.received | 08:33:35
 ai.geocode      | 08:33:35
 ai.triage       | 08:33:37
 ai.trust        | 08:33:37
 ai.allocation   | 08:33:37
```

### 8.2 Badalne/mitane ki koshish karein (in ko **fail** hona chahiye)

Ek ek kar ke chalayein:
```sql
UPDATE audit_logs SET action = 'hacked' WHERE incident_id = 4;
DELETE FROM audit_logs WHERE incident_id = 4;
UPDATE incidents SET original_text = 'changed' WHERE incident_id = 4;
```
**Sahi output:**
```
ERROR:  audit_logs rows cannot be changed or deleted (NFR-C10)
ERROR:  audit_logs rows cannot be changed or deleted (NFR-C10)
ERROR:  incidents.original_text cannot be changed once saved
```
✅ Pass: teeno **ERROR** dein. (Yahan error aana hi kamyabi hai — safety rule 9.)

### 8.3 AI worker zinda hai (heartbeat)

```sql
SELECT worker_id, last_seen_at::time(0), info FROM worker_heartbeats ORDER BY last_seen_at DESC LIMIT 1;
```
**Sahi output:** `info` mein `"llm_ready": true`, `"llm_model": "openai/gpt-oss-120b"`, `"jobs_done": <number>`, `"jobs_failed": 0`. `stt_ready: false` theek hai (awaaz wala hissa abhi nahi bana).

---

## Step 9 — Automatic tests

Terminal 2 mein:
```bash
python3 scripts/run_project.py test
```
**Sahi output** (aakhir mein, ~1.5 minute):
```
SKIPPED [1] tests/api/test_api_contract.py:98: docs/API_CONTRACT.md not visible here ...
SKIPPED [1] tests/api/test_rbac_matrix.py:75: docs/API_CONTRACT.md not visible here ...
SKIPPED [1] tests/unit/schemas/test_events.py:176: docs/API_CONTRACT.md not visible here ...
887 passed, 3 skipped in 79.42s

   RESULT: all tests passed
```
- 3 skip normal hain (ye docs folder dekhte hain jo container ke andar nahi). Poora repo ke saath chalane par ye bhi chalte hain:
  ```bash
  docker compose run --rm -v "$PWD":/repo -w /repo/backend api pytest -q -rs
  ```
  → **890 passed, 0 skipped**.
- Tests aap ke asli data ko **nahi** chhooti; ye alag `dispatch_test` database par chalti hain.

✅ Pass: `0 failed`.

---

## Step 10 — Jo abhi nahi bana (ye `501` dena chahiye)

Ye endpoints contract mein hain lekin abhi bane nahi. Inhe kholein to **501** aur task number aana **sahi** hai (koi jhoota "success" nahi):

| Endpoint | Sahi output |
|---|---|
| POST /api/v1/driver/duty/start (driver token) | `501` … `B1-A1-27` |
| GET /api/v1/admin/users (admin token) | `501` … `B1-A1-31` |
| POST /api/v1/reports/{ref}/confirmation | `501` … `B1-A1-24` |
| POST /api/v1/reports/voice (audio file ke saath) | `501` … `B1-A1-17` |

Abhi nahi bana: dispatch approval aur gaari lock, driver duty/GPS, admin panel, voice/SMS reports, duplicate detection (Coordination Agent), jagah ke naam se location (geocoding), asal road route (OSRM), live dashboard, mobile app.

---

## Step 11 — Band karna

- Sirf AI worker: Terminal 1 mein **Ctrl+C**.
- Sab kuch (data mehfooz rehta hai):
  ```bash
  python3 scripts/run_project.py stop
  ```
- Kya chal raha hai: `python3 scripts/run_project.py status`

> ⚠️ `docker compose down -v` **mat** chalayein — ye poora database (sab reports) mita deta hai.

---

## Step 12 — Browser mein report page (citizen ka page)

Is ke liye Node.js 22.12 ya naya chahiye (`node -v`). Pehli dafa script khud packages install karegi.

1. **Terminal 1** mein backend chal raha ho (Step 1: `python3 scripts/run_project.py`).
2. **Terminal 2** mein:
   ```bash
   python3 scripts/run_project.py web
   ```
   **Sahi output:**
   ```
   ==> Starting the web pages. Press Ctrl+C to stop them.
      - report page : http://localhost:5174
      - dashboard   : http://localhost:5173
   ```
3. Browser mein **http://localhost:5174** kholein.

### 12.1 Page dekhein
✅ Pass agar:
- Sab se upar laal dabbe mein **"If life is in danger, also call 1122."** hai.
- Peeli warning **nahi** hai (backend chal raha hai). Backend band karein to ~15 second mein "Cannot reach the server." aata hai, aur 1122 wala dabba phir bhi rehta hai.
- **"Record voice (coming soon)"** button dabta nahi (voice abhi nahi bana).
- Mobile size par bhi theek dikhta hai (Chrome mein F12 → phone icon → 360 px).

### 12.2 Apni report bhejein
1. "What happened?" mein likhein, masalan: `SIMULATED: Clock Tower ke paas bus accident, 3 log zakhmi`
2. **"Use my location"** dabayein → browser ijazat maange to **Allow** → `Your location is added (accurate to about … m).`
   (Inkaar karein to: `Location permission was refused. Please type the place or a landmark below.` — report phir bhi ja sakti hai.)
3. Optional: "Place or landmark" mein `near Clock Tower`, naam, phone `0300 1234567`.
4. **Send report** dabayein.

**Sahi output:** hari screen **"✔ Report saved"**, bara reference number, masalan **`INC-000012`**, aur "Your report is saved and is in the dispatcher's queue."
Database mein check (Step 0 wala tareeqa):
```sql
SELECT reference_no, channel, status, location_text, location_source, client_request_id
  FROM incidents ORDER BY incident_id DESC LIMIT 1;
```
→ wahi reference, `channel = web`, aap ka landmark, GPS di thi to `location_source = gps`. AI worker chal raha ho to kuch second baad `status = triaged` (Step 4.2 wali query).

### 12.3 Ghalat form
| Kya karein | Sahi nateeja (koi request nahi jati) |
|---|---|
| Khaali "What happened?" ke saath Send | `Please describe what happened.` aur cursor us box par |
| Phone mein `abc` | `Use digits only, for example 0300 1234567.` aur box laal |
| 2000 se zyada characters | neeche ginti laal `2001 / 2000` aur `Too long: at most 2000 characters.` |

### 12.4 Network band ho to (TC-04)
1. Form bharein. Phir F12 → **Network** tab → **Offline** chunein → **Send report**.
   → `Your report was not sent: no connection. … it will not be sent twice.` (koi reference number **nahi**)
2. **Online** wapas karein → **Send report** dobara.
   → "Report saved" aur reference number. Database mein ye report **sirf ek dafa** honi chahiye:
   ```sql
   SELECT client_request_id, count(*) FROM incidents GROUP BY 1 HAVING count(*) > 1;
   ```
   → `(0 rows)`

### 12.5 Database band ho to (503)
Terminal 2 mein `docker compose stop postgres`, page par report bhejein:
→ `Your report was NOT saved. If life is in danger, call 1122 now.` — **koi reference number nahi**, aap ka likha text form mein mehfooz.
Phir `docker compose start postgres`, 10 second baad dobara Send → "Report saved".

### 12.6 Urdu
Upar **اردو** button → poora page right-to-left, labels Urdu mein ("کیا ہوا ہے؟", "رپورٹ بھیجیں"), 1122 notice: "اگر جان کو خطرہ ہو تو 1122 پر بھی کال کریں۔". Urdu mein report likh kar bhejein → "رپورٹ محفوظ ہو گئی". **English** button se wapas.

Band karna: Terminal 2 mein **Ctrl+C** → `Web pages stopped.`

### 12.7 Web ke automatic tests
```bash
python3 scripts/run_project.py test-web
```
**Sahi output** (aakhir mein):
```
   tests     : passed
   typecheck : passed
   build     : passed
```
(Upar kahin `Tests  130 passed (130)` bhi likha hoga.)

---

## Step 13 — Dashboard: login aur roles

Backend aur `python3 scripts/run_project.py web` chal rahe hon (Step 12). Browser mein **http://localhost:5173** kholein.

### 13.1 Bina login
**Sahi output:** khud **http://localhost:5173/login** par aa jata hai: "Sign in" form. http://localhost:5173/queue seedha kholein → wapas login.

### 13.2 Dispatcher
Username `dispatcher1`, password = aap ka `SEED_DISPATCHER_PASSWORD` → **Sign in**.
**Sahi output:** address `/queue`, upar "AMCEDS — Dispatcher Dashboard", "Incident queue" link, `Signed in as SIMULATED Dispatcher One (Dispatcher)`, aur neeche incident queue (Step 14).
Ab address bar mein `/admin` likhein → **"Not allowed — Your role may not open this page."** aur "Go to my start page" link.

### 13.3 Admin
**Sign out** → "You have signed out." Phir `admin1` + `SEED_ADMIN_PASSWORD` → address `/admin`, "Administration is not built yet (task B1-A1-31)." `/queue` kholein → "Not allowed".

### 13.4 Driver
`driver01` + `SEED_DRIVER_PASSWORD` → **"Drivers use the mobile app, not the dashboard. You have been signed out."** (login page par hi rehta hai).

### 13.5 Ghalat password aur lock (TC-32)
`dispatcher2` + ghalat password → "Wrong username or password." aur password box khaali. 5 dafa ghalat → "Too many wrong passwords. The account is locked; try again in 15 minute(s)." Unlock (Step 7.4 wali SQL):
```sql
UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE username = 'dispatcher2';
```

### 13.6 Sign out aur reload
- **Sign out** → "You have signed out.", database mein `auth.logout` audit row:
  ```sql
  SELECT l.action, u.username, l.created_at::time(0) FROM audit_logs l JOIN users u USING (user_id)
   WHERE l.action LIKE 'auth.%' ORDER BY l.log_id DESC LIMIT 4;
  ```
- Login ke baad page **reload (F5)** karein → dobara login maangta hai. Ye **sahi** hai: token sirf memory mein rehta hai (zyada mehfooz).

### 13.7 Idle logout (optional, 30 minute)
Login karke 28 minute kuch na chhooein → peeli pati "No activity for a while: you will be signed out in 2 minutes." aur **Stay signed in** button. Kuch na karein → 30 minute par login page: "You were signed out after 30 minutes without activity." (Itna intezar na karna ho to ye automatic tests mein nakli ghadi se check hota hai: Step 12.7.)

---

## Step 14 — Dashboard par AI ke nateeje (queue aur review)

Backend (AI worker ke saath, Step 1) aur `python3 scripts/run_project.py web` chal rahe hon.

### 14.1 Data tayyar karein
1. Gaariyon ka mashwara dekhne ke liye drivers on-duty karein (Step 5.1 wali SIMULATED SQL — sirf 60 second chalti hai):
   ```sql
   UPDATE users SET on_duty = true WHERE role = 'driver';
   UPDATE vehicles SET last_seen_at = now();
   ```
2. Usi minute mein 2–3 reports bhejein (report page http://localhost:5174 se, ya Step 4.1 ke `curl` se) — masalan ek accident GPS ke saath, ek Urdu aag, ek ghair-wazeh ("kuch ho gaya hai jaldi aao").

### 14.2 Queue
http://localhost:5173 → `dispatcher1` se login → **Incident queue**.
**Sahi output** (asal run, 2026-11-22):
```
▲▲ Critical  Accident  INC-000001  Triaged   1 min ago   📍 GPS 27.7100, 68.8500   Trust: Medium (60)   ⚠ Not enough vehicles
?  Severity unknown  Type unknown  INC-000003  Needs check  📍 Location unknown  Trust: Low (35)
   ⚠ Location unknown  ⚠ Low trust — urgent, not held back  ⚠ More information needed
■  Medium  Fire  INC-000002  Triaged   📍 GPS 27.7000, 68.8600   Trust: Medium (60)
```
✅ Pass agar:
- Tarteeb: **critical → high → severity maloom nahi → medium → low**; ek hi severity mein purani report upar.
- Har card par rang ke saath **likha hua** severity, type, reference, waqt, jagah, trust aur flags.
- Abhi bheji report pehle **"⏳ AI is reading this report…"** dikhati hai, 5–10 second mein khud badal jati hai (page reload ki zaroorat nahi — har 5 second refresh).
- Nayi **critical** report aaye to upar **"🔴 1 new critical report(s)"** aur card laal chamakta hai.
- Upar `Updated hh:mm:ss` har 5 second badalta hai. Doosre tab par jayein → refresh rukta hai; wapas aayein → turant refresh.

### 14.3 Review screen
Kisi card par click → `/incidents/<id>`.
**Sahi output** (accident wali report, asal run):
- **Report as received:** report bilkul waisi jaisi bheji (Urdu ho to right-to-left), reporter ka naam, "via Web".
- **What the AI understood** + "🤖 AI recommendation — dispatcher decides":
  `Type Accident — Type: 96%`, `Severity ▲▲ Critical — Severity: 85%`, `People hurt 7 — 80%`, `Language — 95%`, aur `Overall`.
  Koi value 60% se kam ho to us ke saath **"Dispatcher must check"**.
- **Trust:** `Trust: Medium (60)`, "Every report starts at 50.", `+10 the message names a place, an event or people hurt`.
- **Why the dispatcher should look:** review reasons saaf alfaaz mein (masalan "Not enough vehicles").
- **Recommended vehicles:**
  ```
  1  SIM-AMB-03  Ambulance  0.8 km  1 min  ≈ Approximate
  2  SIM-AMB-01  Ambulance  0.9 km  1 min  ≈ Approximate
  3  SIM-AMB-02  Ambulance  2.6 km  4 min  ≈ Approximate
  4  SIM-BKP-01  Backup     5.0 km  7 min  ≈ Approximate
  ```
  aur kami ho to laal "Not enough vehicles: … missing."
- **Approve dispatch** button **dabta nahi**, neeche: "Dispatch approval is not built yet (task B1-A1-25). No vehicle is sent from this screen."

Ghair-wazeh report kholein → AI values mein "not known", "More information needed", aur gaariyon ki jagah "No vehicle could be recommended…".
Address bar mein `/incidents/99999` → "There is no incident with this number." `admin1` se `/incidents/1` → "Not allowed".

### 14.4 API seedha (optional)
http://localhost:8000/docs → **Authorize** (dispatcher token) → **GET /api/v1/incidents** → 200 aur list; `severity=unknown` filter sirf woh reports deta hai jin ki severity abhi tay nahi. **GET /api/v1/incidents/{id}** → `recommendations[].plate_number` maujood.

---

## Aakhri checklist — tick karte jayein

| # | Check | Sahi nateeja | ✔ |
|---|---|---|---|
| 1 | Script start | `API is up: {"api":"ok","database":"ok"}`, Groq model available, worker `starting with 2 slot(s)` | ☐ |
| 2 | Database | 15 tables, 35 settings, 9 users, 6 vehicles, 2 hospitals | ☐ |
| 3 | Sahi report | `HTTP 201` + `INC-000…` | ☐ |
| 4 | Dobara same report | `HTTP 200`, same reference | ☐ |
| 5 | 5 ghalat forms | sab `HTTP 422 validation_error` | ☐ |
| 6 | Accident report | `accident`, `triaged`, victims sahi | ☐ |
| 7 | Urdu report | `language = Urdu`, type sahi | ☐ |
| 8 | Vague report | `needs_check` + `missing_info` | ☐ |
| 9 | Trust | har point ki wajah likhi | ☐ |
| 10 | Mashwara | qareeb gaari rank 1, `eta_is_approximate = t`, gaariyan `available`, assignments `0` | ☐ |
| 11 | Worker band → report | `201`, `pending`, worker chalne par `done` | ☐ |
| 12 | AI fail | `needs_check`, `failed`, `{ai_failed}` | ☐ |
| 13 | Login | `200`, `expires_in: 900` | ☐ |
| 14 | /auth/me | apna naam aur role | ☐ |
| 15 | Roles | dispatcher→admin `403`, driver→incidents `403` | ☐ |
| 16 | 5 ghalat password | `account_locked` | ☐ |
| 17 | Logout | `204`, phir purana token `session_ended` | ☐ |
| 18 | Audit/original text badalna | teeno `ERROR` | ☐ |
| 19 | Heartbeat | `llm_ready: true` | ☐ |
| 20 | Automatic tests | `887 passed, 3 skipped`, `0 failed` | ☐ |
| 21 | Na bane endpoints | `501` + task number | ☐ |
| 22 | Report page khulta hai | 1122 notice, peeli warning nahi, voice button band | ☐ |
| 23 | Browser se report | "Report saved" + `INC-…`, database mein `channel = web` | ☐ |
| 24 | GPS / inkaar | location added / "permission was refused", report phir bhi jati hai | ☐ |
| 25 | Ghalat form | request nahi jati, saaf message | ☐ |
| 26 | Offline → online | pehle "not sent", phir saved; database mein sirf ek dafa | ☐ |
| 27 | Database band | "NOT saved … call 1122", reference nahi | ☐ |
| 28 | Urdu | RTL, Urdu labels aur notice | ☐ |
| 29 | Web tests | tests, typecheck, build sab `passed` | ☐ |
| 30 | Dashboard bina login | `/login` par bhej deta hai | ☐ |
| 31 | Dispatcher login | `/queue`, naam aur role, `/admin` par "Not allowed" | ☐ |
| 32 | Admin login | `/admin`, `/queue` par "Not allowed" | ☐ |
| 33 | Driver login | "Drivers use the mobile app", sign out | ☐ |
| 34 | Ghalat password / lock | saaf message, 5 ke baad locked | ☐ |
| 35 | Sign out / reload | "You have signed out.", reload par dobara login | ☐ |
| 36 | Queue ki tarteeb | critical → high → unknown → medium → low | ☐ |
| 37 | Queue ka refresh | nayi report khud aati hai, "AI is reading" phir nateeja | ☐ |
| 38 | Nayi critical | "🔴 new critical report(s)" aur laal card | ☐ |
| 39 | Review: AI | har value ke saath confidence, 60% se kam par "Dispatcher must check" | ☐ |
| 40 | Review: trust aur reasons | har point ki wajah, review reasons saaf alfaaz mein | ☐ |
| 41 | Review: gaariyan | plate, km, minute, "≈ Approximate" | ☐ |
| 42 | Approve dispatch | button band, "not built yet (B1-A1-25)" | ☐ |

Agar koi check fail ho: us ka **command aur poora output** copy karke bhejein, hum wajah dhoond kar theek karenge.
