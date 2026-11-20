# Part 8 — Android mobile application (React Native)

Authority: SRS SW-9, UC-01, UC-08, UC-09, UC-11, CI-3, CI-7; SDS Table 4.1 and §7.4; **D-002 approved** (React Native in `mobile/`). **Still open:** Expo with a development build vs bare React Native; whether `frontend/pwa` is renamed. Owner: Khalid (Agent 3, A-007/D-027b assumption: the slide does not name the app — team to confirm).

One Android app (Android 9+, SRS NFR-P17) with two modes: **citizen** (no login) and **driver** (login, role `driver`).

## 8.1 Citizen mode (UC-01)

| Feature | Design |
|---|---|
| Submit text report | same fields as the web page; **"If life is in danger, also call 1122"** always visible (NFR-S7) |
| Location | foreground location permission; fallback typed landmark; none allowed (TC-03) |
| Voice report | record ≤ 2 min, preview, upload to `/reports/voice` |
| Reference number | shown only after the API confirms the save |
| Offline | report saved on the phone with its `client_request_id`; sent automatically when the network returns; shows "sent" / "waiting for network"; exactly one record is created (TC-04, CI-7) |
| Language | English and Urdu UI (RTL); Sindhi text accepted |

## 8.2 Driver mode (UC-08, UC-09, UC-11)

| Step | Behaviour | Notes |
|---|---|---|
| Login | personal account; lockout and idle rules from the server | a driver with an open assignment is not logged out for idleness (UC-11 1b) |
| **Start Duty / End Duty** | big buttons; Start begins GPS sharing, End stops it | **GPS is never sent off duty** (NFR-C5, TC-33); End Duty is refused while an assignment is open |
| Assignment alert | red banner + sound; severity, type, place, patients, ETA; mini-map with route preview; two large buttons **Accept** / **Cannot Go** (reason from a pick-list, no typing); 60-s countdown | arrives by WebSocket, FCM when configured, SMS backup (D-013) |
| Navigate | Accept opens navigation **at once with no typing**: in-app map with the OSRM route (`GET /routing/route`), step list, voice prompts (text-to-speech), re-route when more than ~50 m off the line for 3 fixes; one-tap fallback to an external navigation app | D-016 (open); cached pilot-area tiles for weak network (UC-08 3a, D-028) |
| GPS sharing | about every 5 s while on duty, in batches after a network drop; server keeps the newest point | NFR-P4; `client_point_id` dedups |
| Trip status | auto **On scene** within 100 m of the incident, auto **At hospital** on arrival; manual **Patient picked up** (opens hospital navigation) and **Available**; manual On scene fallback | one large "next step" button (SDS §7.4 item 7); hospital change from the dispatcher appears with a "new information" banner (UC-08 4a) |
| Work through short network interruptions | GPS points and status updates queued locally and flushed in order; assignment already on screen stays usable | CI-7 |

## 8.3 How the hard parts will be implemented

### GPS and Android background limits

- Android can stop apps that run in the background. The plan: a **foreground service with a visible notification** only while on duty; permission flow for fine location and (Android 10+) background location only if testing shows it is needed; battery-optimisation exemption instructions in the one-page driver guide.
- Library choice (background-location package, Expo module vs bare) is made in B1-A3-13 after a **two-day spike on a real Android 9 and a recent Android phone**; the decision is recorded in DECISIONS_LOG. Until the spike passes, background GPS is **not verified** (risk R5).
- The app asks for location only after Start Duty (citizen mode asks only when the person taps *Use my location*).

### Notifications

1. Primary for the demo: the **WebSocket** to the logged-in app (assignment appears within 5 s, NFR-P5).
2. FCM push when a Firebase project exists (`google-services.json` needed; **D-013 open**).
3. If neither reaches the driver: the dispatcher sees a warning and an SMS (simulated) is sent (UC-06 4b).
Sound alert uses a high-priority notification channel; the app must be allowed to play sound while the screen is off.

### Offline synchronisation

| Data | Local store | Sync rule |
|---|---|---|
| Citizen reports | persistent queue (SQLite/AsyncStorage) with `client_request_id` | send on connectivity change; 201 or "already exists" removes it |
| GPS points | ring buffer, max a few hundred points | send as one batch, oldest first; server ignores duplicates |
| Status updates | ordered queue | replay in order; server rejects invalid transitions with 409 (shown to the driver) |
| Assignment | last known assignment cached | refreshed on reconnect through `GET /driver/assignments/current` |

### Maps and TLS in development

- OSM tiles with attribution; pre-cache the pilot area (D-028).
- The demo server uses a local CA over HTTPS (D-024); a debug build may trust it through Android network-security-config; **never** ship that setting in a release build.

## 8.4 Screens

Citizen: Home/Report, Voice recorder, Sent (reference). Driver: Login, Duty, Assignment alert, Navigation (with trip status bar), Trip status, Settings/Language.

## 8.5 Testing the app

- Unit tests: offline queue (one POST after reconnect), geofence (99 m vs 101 m), no location calls off duty (mocked location API), reason-code buttons only.
- Device checklist `docs/test-reports/mobile_checklist.md` mapping TC-04, 26–33, 42, 47 to manual steps on Android 9+.
- Full trip with simulated movement in Batch 3 (B3-03/05) using the vehicle simulator.

## 8.6 Build order

B1-A3-13 scaffold (after D-002 sub-choice + GPS spike) → 15 login/duty/GPS → 16 assignment alert → 17 navigation → 18 trip status → 14 citizen mode (can run earlier in parallel if time allows) → B3 integration on a real device.
