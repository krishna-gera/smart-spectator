# Smart Spectator — Full System Audit

**Audit date:** 28 October 2026
**Repository:** `krishna-gera/smart-spectator` (local checkout at `/Users/krishnagera/smart-spectator`)
**Branch / commit audited:** `main` @ `4467eb2` **plus 96 uncommitted working-tree changes** (see Section 2)
**Audit type:** Static code review, dynamic API checks against a throwaway database, existing test suites, lint. No physical Android phone, Snapdragon PC, or QNN runtime was available.

**How to read the labels in this report**

| Label | Meaning |
|---|---|
| **Verified** | Proven by code reading plus a command or test that was actually run during this audit. |
| **Likely** | Strongly indicated by the code, but not executed end-to-end (usually needs a real phone). |
| **Unverified** | Could not be established with the available environment. |

Earlier reports in `docs/` (for example `docs/AUDIT_REPORT.md`, `docs/FINAL_PROJECT_REPORT.md`) were **not** treated as evidence. Where this audit disagrees with them, this audit says so and gives the proof.

---

## 1. Executive Summary

**What the repository contains.** A Python/FastAPI "hub" (`services/`), a plain-JavaScript web dashboard served by the hub (`apps/client/`), an Android-only Flutter camera app (`apps/camera/`), AI code and model files (`ai/`), about 100 REST/WebSocket endpoints, a SQLite database with WAL and migrations, and 176 passing Python tests.

**What works (Verified).**
- The hub starts its components, creates the database in WAL mode and runs migrations.
- The binary video packet format (24-byte header + H.264) is implemented the same way on the phone and the hub.
- The hub can decode real H.264 with PyAV and serve a live MJPEG preview (covered by `tests/integration/test_real_h264_decode.py`).
- The event engine, rules, zones, recordings, retention, backup/restore, and auth/RBAC modules work in isolation and are well covered by unit tests.
- The ByteTrack-style tracker (Kalman filter + IoU matching) is real code.
- The Flutter app passes `flutter analyze` with no issues.

**The four most important problems.**

1. **There is no real object detector.** The file `ai/models/yolov8n.onnx` is **not YOLOv8n**. It is a tiny, randomly initialised network built by `scripts/export_detection_model.py`. That script hard-codes a "person" score near 0.88. When run during this audit, it reported `person 0.88` on an all-black frame, an all-white frame and random noise. On top of that, the hub never loads the detector at all (`detector.load()` is never called at startup), so every live frame currently gets **zero detections**. In short, the AI pipeline runs but cannot see anything.
2. **A phone cannot pair with the hub, and could not stay connected if it did.**
   - Pairing: every press of "Pair" on the phone asks the hub for a *new* PIN before checking the one the user typed. The PIN the user read is therefore always out of date (reproduced: 400 "Invalid verification code").
   - Staying connected: when the phone's control connection closes, the hub marks the device `disconnected`. The token check only accepts `paired` or `connected`, so the token stops working **after the first disconnect**. Every reconnect, and every "Start Streaming" after a "Stop", is then rejected.
3. **The web dashboard is never logged in.** It has no login screen. Its `login()` helper also reads `res.token`, but the backend returns `access_token`. Every protected page (devices, pending pairing PINs, events, recordings, zones, rules) gets 401 errors. Only the endpoints that are left **open** work, and those include the live camera preview.
4. **Live video and many controls have no authentication.** On the LAN, anyone can watch any camera (`/api/v1/streams/{id}/preview` and `/snapshot`), stop or rename cameras, change notification settings, read incidents, and run event queries. A device's camera token also has *higher* rank than a human "viewer", so a token taken from a phone can read all events and recordings.

**Other major risks.** About 4,000 lines of work exist only on this laptop: the entire auth system, `requirements.txt`, and the H.264 encoder bridge are staged but not committed, and 37 commits are not pushed. SpectatorNet is trained on synthetic data only, and its own INT8 evaluation shows 14% accuracy. The pre-event buffer keeps raw frames, which is roughly 830 MB of RAM per camera (estimated). CI is likely to fail: flake8 finds an error, and the Flutter version in CI is older than the app needs.

**Most important next step.** Commit and push the local work. Then fix the device connection path (PIN flow, token status bug, camera-to-token binding), lock down the open video endpoints, and add a login to the dashboard. After that, replace the placeholder detector with real YOLOv8n weights and load it at startup. Until these are done, a real phone cannot produce a single real event.

---

## 2. GitHub Synchronization Status

| Item | Result |
|---|---|
| Repository root | `/Users/krishnagera/smart-spectator` (Verified) |
| Remote | `origin` → `https://github.com/krishna-gera/smart-spectator.git` |
| Branch / upstream | `main` tracking `origin/main` |
| Starting commit | `4467eb2` — "feat: implement Phase 10 query engine, incident management…" |
| Fetch | `git fetch --all --prune` ran successfully |
| Comparison after fetch | Local is **37 commits ahead, 0 behind** `origin/main` (`origin/main` = `8034b37`) |
| Pull | **Not needed.** There was nothing new on GitHub, so no pull was run. |
| Final commit | `4467eb2` (unchanged) |
| Working tree | **96 changed paths**: 23 staged new files, 66 modified, 7 both staged and modified, 1 untracked (`docs/ENGINEERING_REMEDIATION_PLAN.md`). `git diff HEAD --stat`: 4,063 insertions, 786 deletions. |
| Synchronized? | Nothing to pull. **GitHub is behind this laptop**: 37 local commits plus all uncommitted work are not on GitHub. |

**Why this matters.** These files exist only on this machine: `services/hub_backend/auth/*` (all authentication), `requirements.txt`, `apps/camera/lib/core/codec/h264_encoder.dart` (the phone's encoder bridge), `services/hub_backend/routes/auth.py`, all database repositories, `tests/conftest.py`, and `tests/test_auth_rbac.py`. A fresh clone from GitHub would not include them. The audit below covers the **working tree as it is on disk**.

Nothing was pushed, committed, reset, or stashed during this audit.

---

## 3. Application Inventory

| Component | Directory | Purpose | Current Status | Evidence |
|---|---|---|---|---|
| Hub backend (FastAPI) | `services/hub_backend/` | REST + WebSocket API, startup orchestration | **Implemented** (with auth gaps) | `main.py:28-71` lifespan; ~100 routes enumerated during audit |
| Stream engine | `services/stream_engine/` | Packet parsing, H.264 decode, per-camera sessions | **Partially implemented** | WebSocket ingest works; TCP ingest is a dead end (§8) |
| Device manager | `services/device_manager/` | Pairing, device tokens, mDNS advertising | **Implemented but broken in practice** | PIN and token-status bugs (§8) |
| AI perception pipeline | `services/ai_engine/` | Frame sampling, detection, tracking, observations | **Partially implemented / disconnected** | Detector never loaded (`detector.py:51`, no `load()` call in `main.py`) |
| "YOLOv8n" detector model | `ai/models/yolov8n.onnx`, `ai/models/releases/detector_v1.onnx` | Object detection | **Mocked** (random-weight placeholder) | `scripts/export_detection_model.py:20-73`; audit run gave `person 0.88` on a black frame |
| ByteTrack tracker | `services/ai_engine/tracker.py` | Multi-object tracking | **Implemented** (only ever fed empty or fake input) | Kalman filter `:36-107`, two-stage tracker `:179` |
| SpectatorNet | `ai/models/spectatornet.py`, `ai/models/predictor.py`, `.onnx` files | Temporal event classification | **Implemented, not usefully trained** | BiGRU over 166 hand-made features (no MobileNetV3); synthetic-only data; INT8 eval accuracy 0.14 |
| QNN / accelerator layer | `ai/inference/manager.py` | QNN → DirectML/CoreML → CPU fallback | **Implemented, QNN unverified** | `:137-224`; on this Mac only CoreML/CPU exist |
| Event engine | `services/event_engine/` | Confidence filter, debounce, rules, zones, severity, actions, incidents, anomalies | **Implemented** (no real input) | 176 passing tests; `engine.py:185-345` |
| Recording manager | `services/event_engine/recorder.py` | Pre-event buffer, MP4 clips | **Partially implemented** | ~10 s raw-frame buffer (`:129`), `mp4v` codec (`:224`) |
| SQLite database | `services/hub_backend/database/` | Persistence, WAL, migrations, backup | **Implemented** | `connection.py:22-47`, `migrations.py:411-440` |
| Retention | `services/hub_backend/storage/retention.py` | Delete old recordings/events | **Partially implemented** | Runs only on demand or after a clip; `event_predictions` is never pruned |
| Web dashboard | `apps/client/` | Operator UI (vanilla JS, served at `/`) | **Implemented UI, disconnected from auth** | No login UI; `api.js:318-323` reads the wrong field |
| Legacy inline dashboard | `services/hub_backend/main.py:146-366` | Fallback HTML when `apps/client` is missing | **Unused** | `CLIENT_DIR` exists, so `/` always serves `apps/client/index.html` |
| Android camera app (Flutter) | `apps/camera/` | Pair, capture, encode, stream | **Partially implemented** | Capture → MediaCodec → WebSocket is written; pairing and reconnect are broken; YUV handling likely wrong |
| iOS camera app | — | — | **Missing** | No `apps/camera/ios/` directory |
| Mobile companion / client app | — | — | **Missing** | Not found in the repo |
| Desktop app | `apps/hub/` | — | **Missing** (empty directory) | `ls apps/hub` → empty |
| Local LLM query adapter | `ai/orchestration/` | Optional Ollama-backed natural-language query | **Optional, local only** | `llm_adapter.py:170` defaults to `127.0.0.1:11434` |
| Windows deployment scripts | `scripts/*_windows.ps1` | Install/start/stop as a service | **Unverified** | Not runnable on macOS |
| CI | `.github/workflows/ci.yml` | Lint, bandit, pytest, Flutter analyze, QNN job | **Likely failing** | flake8 F821 errors; Flutter 3.24 vs Dart SDK `^3.12.0` |

---

## 4. Current Architecture

### 4.1 What the code actually does today

```
ANDROID PHONE (Flutter app, apps/camera)                            iOS: MISSING
  CameraController.startImageStream (YUV420)
        │  planes concatenated (row padding/stride ignored)  ← LIKELY BROKEN
        ▼
  MethodChannel → MainActivity.kt MediaCodec H.264 (runs on main thread)
        ▼
  PacketEncoder (24-byte SS header)  ── matches hub protocol ✔
        ▼
  WebSocket  ws://HUB:8000/api/v1/streams/ingest/{camera_id}?token=…
        │       (plain ws://, token in URL)
        │  ✖ PAIRING: PIN regenerated on every attempt → cannot pair from the app
        │  ✖ TOKEN dies after first control-socket disconnect
        ▼
LOCAL HUB  (FastAPI, single uvicorn worker, 0.0.0.0:8000)
  streams.py ingest WS ──► stream_engine.process_binary_chunk  (decode on event loop)
        │                        │
        │                        ├──► RecordingManager rolling buffer (raw frames, ~10 s)
        │                        └──► ai_pipeline.submit_frame
        │                                  ▼
        │                      AdaptiveFrameSampler (~5 fps) → bounded queue (2)
        │                                  ▼
        │                      YOLOObjectDetector.detect()
        │                         ✖ never loaded → returns []
        │                         ✖ even if loaded: placeholder model, always "person 0.88"
        │                                  ▼
        │                      ByteTrackTracker (real) → Observation
        │                                  ▼
        │                      EventEngineService.on_observation
        │                         SpectatorNet ONNX (synthetic-trained) ~1 Hz
        │                                  ▼
        │                      EventEngine: confidence → debounce → rules → severity
        │                         → events / event_predictions / recordings (SQLite WAL)
        │                         → incidents / anomalies / relationships
        │                                  ▼
        │                      WebSocket /api/v1/events/stream (NO AUTH)
        │
  TCP :8554 ingest ── camera_id hard-coded "default", no auth,
                      frames never sent to AI or recorder  (DEAD END; app does not use it)
  mDNS advertiser (zeroconf) ── the app does not use mDNS (it probes guessed IPs)
        ▼
WEB DASHBOARD (apps/client, served at http://HUB:8000/)
  ✔ Live MJPEG preview (works because it is unauthenticated)
  ✖ Devices, pending PINs, events, recordings, rules, zones → 401 (never logs in)
  ✖ Recording <video>/<img> cannot send Authorization header → 401 even after login
```

### 4.2 In plain English

- **Phone → hub.** The phone captures frames, hardware-encodes them to H.264, wraps each chunk in a small header, and sends it over a WebSocket on port 8000. A second WebSocket (`/api/v1/control/ws`) sends battery telemetry once a second. The phone finds the hub by trying a few guessed IP addresses (`.1`, `.2`, `.10`…) on its subnet. It does not use the mDNS announcement the hub sends out.
- **Hub video.** The hub decodes H.264 with PyAV. It keeps the latest frame for the live preview, copies every frame into a rolling buffer for clips, and passes about 5 frames per second to the AI worker thread.
- **Where AI runs.** AI runs inside the hub process: one background thread for detection and tracking, and SpectatorNet inside the observation callback. It uses ONNX Runtime with QNN → DirectML/CoreML → CPU fallback. On this Mac, CoreML and CPU are available. QNN could not be tested.
- **Events.** SpectatorNet output goes through confidence and debounce filters. Confirmed events are stored in SQLite, can trigger a clip, and are pushed to the browser over `/api/v1/events/stream`.
- **Clients.** The only user interface is the browser dashboard served by the hub. There is no companion mobile app and no desktop app.
- **Cloud.** No cloud service is needed. The only outbound HTTP call in the Python code is to an optional local Ollama server at `127.0.0.1:11434` (`ai/orchestration/llm_adapter.py:110-133`). Verified by grep: no other `requests`/`httpx`/`urllib` calls in `services/`, `ai/`, `shared/`.

### 4.3 Differences from the intended architecture

| Intended | Actual |
|---|---|
| YOLOv8-Nano detection | Placeholder random-weight network named `yolov8n.onnx`, and it is never loaded |
| SpectatorNet = MobileNetV3 + BiGRU | Feature-projection + BiGRU + attention over 166 track-derived features. **No MobileNetV3 and no pixel input** (`ai/models/spectatornet.py:3`; ONNX input `[batch, 30, 166]`) |
| ~15 s pre-event buffer | 300 frames ≈ **10 s at 30 fps** (`recorder.py:129`; `RECORDING_PRE_ROLL_SECONDS=10`) |
| Separate media and control channels | Yes, two WebSockets. A separate TCP media port exists but is unusable. |
| Android + iOS camera nodes | Android only |
| Mobile client | Not present |

---

## 5. Feature Completion Report

| Feature | Expected Behavior | Current State | What's Missing |
|---|---|---|---|
| Hub discovery | Phone finds hub automatically | **Partial.** Phone probes 8 guessed IPs per subnet plus localhost and the emulator host. Hub advertises mDNS, but nobody listens for it. | Use mDNS (e.g. `nsd`/`multicast_dns`) in the app, or a QR code |
| Device pairing | Operator sees PIN; phone enters it; token issued | **Broken (Verified).** Each "Pair" press creates a new PIN before checking (`pairing_screen.dart:82-96` + `manager.py:41-48`). The PIN is visible only in the hub console log or the (unauthenticated-failing) dashboard. | Separate "request PIN" and "submit PIN" steps in the app; keep the existing PIN if one is still valid |
| Device auth on reconnect | Token keeps working until revoked | **Broken (Verified).** Token rejected after the first control-socket disconnect (`control.py:28-32` + `manager.py:166-172`) | Accept any non-revoked status, or store "revoked" separately from connection state |
| Camera capture + H.264 encode | Real camera → hardware H.264 | **Implemented, not device-verified.** YUV planes copied without honouring row stride / pixel stride (`h264_encoder.dart:23-35`); encoder fixed at 1280×720. | Proper YUV420 → NV12/I420 conversion (or Surface input); run on a real phone |
| Video transport | Low-latency WebSocket with reconnect | **Implemented.** Exponential backoff up to 10 tries (`media_transport.dart:97-125`), but reconnect fails because of the token bug | Fix the token bug; add a `request_idr` handler on the phone |
| Hub decode + live preview | Decode H.264, show live view | **Implemented (Verified by test).** No authentication on the preview. | Auth on preview/snapshot |
| Object detection | YOLOv8n detects people/objects | **Mocked + disconnected (Verified)** | Real weights; call `load()` at startup; health check that fails when it is not loaded |
| Tracking | ByteTrack IDs across frames | **Implemented** | Real detections to track |
| Temporal event model | SpectatorNet classifies events | **Implemented, not trained on real data.** INT8 eval accuracy 0.14 / macro-F1 0.053 (`artifacts/evaluation/eval_spectatornet_v1_int8.json`). Training run claims 1.0 on synthetic validation (`artifacts/runs/…/metrics.json`). | Real labelled dataset; retrain; consistent evaluation |
| Event creation & persistence | Confirmed events in DB + pushed live | **Implemented, starved of input.** Logic is tested. Today's empty observations give `CAMERA_BLOCKED` at 0.32, which is below the 0.70 threshold, so no events. | Real detector |
| Pre-event recording (clips) | ~15 s pre-roll + post-roll MP4 | **Partial.** ~10 s, raw frames in RAM, `mp4v` codec (generally not playable in browsers) | Store encoded H.264 instead of raw frames; use H.264 MP4 |
| Zones & rules | Polygon zones, rule actions | **Implemented** (API + engine + UI pages) | Dashboard login to use them |
| Incidents / anomalies / memory / NL query | Higher-level analytics | **Implemented as rules/statistics.** NL query is regex/template unless Ollama is running. Endpoints are open. | Auth; real events to analyse |
| Web dashboard | Operate the whole system | **UI built, not connected to auth** | Login screen, token handling, media URLs carrying auth |
| Camera start/stop from the hub | Hub tells the phone to start/stop | **Mocked.** Endpoints only change a DB status string (`cameras.py:46-75`); no command reaches the phone | Send commands over the control channel; handle them in the app |
| Device revoke | Revoke + stop stream | **Broken (Verified)** when the camera is streaming: `AttributeError: 'StreamSession' object has no attribute 'stop'` (`devices.py:97-99`) | Call `stream_engine.remove_session()` and close the socket |
| Data retention | Automatic cleanup | **Partial.** No periodic scheduler; `event_predictions` never pruned | Background schedule; cover all growing tables |
| Backup / restore | Admin backup and restore | **Implemented.** Restore path is limited to `BACKUP_DIR` (`system.py:421`) | — |
| iOS support | iOS camera node | **Missing** | Entire platform |
| Background streaming on phone | Keep streaming with screen off | **Missing.** `FOREGROUND_SERVICE` permission declared, no service; app stops streaming when paused (`camera_screen.dart:53-73`) | Foreground service |

---

## 6. Integration and Connection Report

| Source Component | Destination Component | Status | Problem | Required Action |
|---|---|---|---|---|
| Camera app pairing screen | `POST /devices/pair/request` + `/pair/verify` | **DISCONNECTED** (Verified) | App always requests a fresh PIN right before verifying, so the user's PIN is stale | Two-step UI; do not regenerate an unexpired PIN |
| Hub PIN display | Operator | **PARTIAL** | PIN printed to stdout (`manager.py:64`); dashboard's `/pairing/pending` needs a login the dashboard cannot do | Fix dashboard login; stop logging PINs |
| Camera control socket | Device token check | **DISCONNECTED after first drop** (Verified) | `disconnect()` sets status `disconnected`; `authenticate_token` only allows `paired`/`connected` | Don't use connection status as an auth gate |
| Camera media socket | Stream engine | **CONNECTED** (code); **UNVERIFIED** on a device | Any valid token may push video as **any** `camera_id` (`streams.py:49`) | Check that `camera_id` belongs to the authenticated device |
| Hub → phone commands (`request_idr`, start/stop) | Phone | **MISSING** | Phone ignores incoming messages (`control_client.dart:42-44`, `media_transport.dart:71-73`); camera endpoints never send commands | Implement command handling both ways |
| TCP ingest :8554 | AI pipeline / recorder | **DISCONNECTED** | `camera_id="default"`, no auth, frames never forwarded (`server.py:135-155`) | Remove it or finish it (handshake, auth, forwarding) |
| mDNS advertiser | Phone discovery | **DISCONNECTED** | App has no mDNS client | Add mDNS browse in the app |
| Stream engine | AI pipeline | **CONNECTED** (`server.py:80-81`) | — | — |
| AI pipeline | Detector model | **DISCONNECTED** (Verified) | `ai_pipeline.detector.is_loaded == False`; nothing calls `load()` | Load at startup using `settings.DETECTOR_MODEL_PATH`; report failure loudly |
| Detector | Real-world vision | **MOCKED** (Verified) | Placeholder model returns a fixed "person" | Export the real Ultralytics YOLOv8n |
| Detector/tracker | SpectatorNet | **CONNECTED** (`service.py:36-60`) | Input is empty or fake | — |
| SpectatorNet | Event engine | **CONNECTED** | Model quality is unproven | Retrain on real data |
| Event engine | SQLite | **CONNECTED** | `event_predictions` written ~1/s per camera and never pruned | Retention |
| Event engine | Browser (events WS) | **CONNECTED, no auth** | `/api/v1/events/stream` accepts anyone (`websocket/events.py:133`) | Token check on connect |
| Backend REST | Web dashboard | **DISCONNECTED** for protected routes (Verified) | No login UI; `res.token` vs `access_token` | Login screen + fix field name |
| Recording/thumbnail URLs | Browser `<video>`/`<img>` | **DISCONNECTED** (Verified 401) | Browser media tags cannot send `Authorization` headers | Short-lived signed media URLs or cookie session |
| Hub | Mobile companion app | **MISSING** | No such app | — |
| Hub | External/cloud services | **None required** (Verified by grep) | Only optional local Ollama | — |

---

## 7. Missing Features

### Confirmed missing

1. **Real object-detection weights.** Without them nothing in the event chain reflects reality. *Component:* `ai/models`. *Blocks:* every AI workflow. *Do:* export the official YOLOv8n (Ultralytics, opset 17, 640×640). Keep its checksum in `manifest.json`. Add a test that it finds nothing in a blank frame and finds a person in a known person image.
2. **Detector loading at startup.** *Component:* `services/hub_backend/main.py`. *Do:* call `ai_pipeline.detector.load(settings.DETECTOR_MODEL_PATH)` in the lifespan. Make `/health` show "degraded" when this fails.
3. **Dashboard login.** *Component:* `apps/client`. *Blocks:* operators cannot see PINs, devices, events, or recordings. *Do:* login form, token storage, logout, and a redirect on 401.
4. **Hub → phone command handling.** Needed for keyframe requests after a decoder reset, and for remote start/stop. *Component:* phone `ControlClient`, hub camera routes.
5. **Phone-side mDNS discovery.** The hub already advertises `_smartspectator._tcp`.
6. **Android foreground service** for streaming with the screen off or the app in the background.
7. **iOS camera app.** Not present at all.
8. **Mobile companion/client app.** Not present. The browser dashboard is the only client.
9. **Periodic retention job,** including the `event_predictions` table.
10. **Encrypted transport (TLS/WSS).** Everything is plain `http://`/`ws://`, and the token travels in the URL query string.
11. **A real (non-synthetic) training/evaluation dataset** for SpectatorNet. All 180 raw sessions are named `syn_*`.

### Status could not be verified

- QNN/Hexagon execution on a Snapdragon PC (no hardware).
- Windows service scripts (`scripts/*_windows.ps1`) (not runnable on macOS).
- Whether the existing debug APK (`apps/camera/build/.../app-debug.apk`, built 15 Oct) matches the current source. It predates the uncommitted `MainActivity.kt` and `h264_encoder.dart` changes.

---

## 8. Broken and Incomplete Features

Each item lists the observed problem and the expected behaviour.

1. **Pairing from the phone always fails (Verified).** `pairing_screen.dart:82-96` calls `requestPairing` and then `verifyPairing` on every tap. `request_pairing` does `INSERT OR REPLACE` with a new PIN (`manager.py:36-48`). The audit reproduced this: request → read PIN → request again → verify with the first PIN → `400 Invalid verification code`. *Expected:* the PIN shown to the operator stays valid until it expires.
2. **Device token stops working after the first disconnect (Verified).** `websocket/control.py:28-32` sets `status='disconnected'`. `manager.py:170-171` only accepts `('paired','connected')`. Audit result: token valid before the control socket closed, invalid after. *Effect:* tapping Stop then Start, or any Wi-Fi drop, needs a full re-pair. Combined with item 1, re-pairing is impossible.
3. **Detector never loaded (Verified)** and **detector model is a placeholder (Verified).** See §1. `services/ai_engine/detector.py:51,183-185`. `scripts/export_detection_model.py:68-71` adds a fixed boost to "person" scores for the first five anchors.
4. **Dashboard cannot authenticate (Verified).** `apps/client/js/api.js:318-323` expects `token`. `routes/auth.py:40-42` returns `access_token`. Nothing in `app.js` calls `login()`.
5. **Recording playback/thumbnails return 401 in the browser (Verified).** `recordings.js:39,89` uses plain URLs in `<img>`/`<video>`. The endpoints need `require_viewer`. `/recordings/x/thumbnail` without a header returned 401.
6. **Revoking a streaming device crashes (Verified).** `routes/devices.py:97-99` calls `StreamSession.stop()`, which does not exist. Result: `AttributeError` → HTTP 500. The device's status is not revoked, because the crash happens first.
7. **TCP ingest server is a dead end.** `services/stream_engine/server.py:130-168`: hard-coded `camera_id="default"`, no auth, and decoded frames never go to AI or the recorder (compare `process_binary_chunk` at `:62-96`).
8. **Phone YUV handling likely corrupts video (Likely).** `h264_encoder.dart:23-35` concatenates Y/U/V planes as-is. On Android, `CameraImage` planes usually have row padding, and the U/V planes are often interleaved (pixel stride 2), which needs conversion before `COLOR_FormatYUV420Flexible` ByteBuffer input. The encoder is also fixed at 1280×720 while the camera chooses its own size (`camera_screen.dart:81,133-139`). *Needs a real-phone test.*
9. **Native encoder can hang (Likely).** `MainActivity.kt:111`: `?: continue` inside the `while` loop never advances `outputBufferIndex`, so a null output buffer loops forever on the main thread.
10. **Camera start/stop/reconnect endpoints are cosmetic.** `routes/cameras.py:46-75` only update a DB string. The phone is never told.
11. **Recordings use `mp4v` (MPEG-4 Part 2)** (`recorder.py:224`). Most browsers will not play this in `<video>` (Likely). Expected: H.264 (`avc1`) MP4.
12. **Pre-event buffer holds raw frames.** 300 × 1280×720×3 bytes ≈ **830 MB per camera** (calculated, not measured), and it is only ~10 s at 30 fps, not the intended ~15 s.
13. **Fallback inline dashboard returns JSON, not HTML.** `main.py:146-366` returns a Python string without `HTMLResponse`. It is unreachable today because `apps/client` exists.
14. **App sends fake device metadata.** `pairing_client.dart:37-39` always sends `'Android Phone'`, `'Android 14'`, `'1.0.0'`. Telemetry `encoder_fps` is hard-coded to 30 (`control_client.dart:77`), and the battery falls back to 85% on error (`:59`).
15. **SpectatorNet evaluation numbers contradict each other.** The training run reports accuracy 1.0 on synthetic validation. The INT8 release evaluation reports 0.14 accuracy / 0.053 macro-F1 on 50 synthetic samples. Neither reflects real-world performance, and the INT8 result suggests the released model is effectively unusable.
16. **Documentation overstates readiness.** `README.md:35-43` marks Phases 2–10 "COMPLETED" with "full REST API authentication" and "YOLOv8n ONNX". `README.md:55` reports a "YOLOv8n Detector" benchmark of 3.38 ms. That is the placeholder network (this audit measured ~4 ms on CPU, far faster than real YOLOv8n). `docs/AUDIT_REPORT.md` calls the detector "REAL, FULLY OPERATIONAL", which this audit disproves.

---

## 9. Security and Privacy Findings

### Confirmed vulnerabilities (Verified by running requests against a test database)

| # | Problem | Why it matters | Component / Evidence | Remediation |
|---|---|---|---|---|
| S1 | **Live video and snapshots need no login** | Anyone on the Wi-Fi can watch every camera. This defeats the privacy goal. | `routes/streams.py:74-105`; route enumeration shows no auth dependency | Require viewer auth (signed short-lived URL or cookie for `<img>`) |
| S2 | **Camera control and config endpoints open** | Anyone on the LAN can rename/stop cameras, disconnect streams, disable notifications | `routes/cameras.py:16-75`; `routes/system.py:618` (PUT notifications): unauthenticated POST/PUT returned 200 | Add `require_operator` |
| S3 | **Event data readable without login** | Incident history, daily summaries, NL query over events, AI detections, diagnostics leak to anyone on the LAN | `/api/v1/incidents`, `/memory/*`, `/query`, `/ai/cameras/{id}/detections`, `/system/diagnostics`, `/feedback*`, `/anomalies*`: returned 200 without a token | Add `require_viewer` to every router by default |
| S4 | **Events WebSocket open** | Live event feed visible to anyone | `websocket/events.py:133-139` | Check token on connect |
| S5 | **Device token outranks "viewer"** | A token extracted from a phone (stored in plain `SharedPreferences`) can read all events, recordings, devices | `auth/roles.py:21` (`DEVICE: 15` > `VIEWER: 10`); a device token got 200 on `/api/v1/events` | Make DEVICE a separate permission set, not a rank above viewer |
| S6 | **Any device can stream as any camera** | One paired phone can inject fake video into another camera's feed, events and recordings | `routes/streams.py:43-56`: `camera_id` comes from the URL and is never checked against the device | Look up the device's camera and reject mismatches |
| S7 | **Unauthenticated TCP listener on 0.0.0.0:8554** | Anyone on the LAN can open sessions, write DB status, and spend CPU on decoding | `stream_engine/server.py:130-168`, `main.py:46` | Remove, or add an auth handshake |
| S8 | **Weak defaults that work outside "production"** | Default admin `admin`/`admin123` and a known HMAC secret are accepted whenever `SMART_SPECTATOR_ENV` is not `production`, which is the default. `start_dev.sh` binds to `0.0.0.0`. The audit logged in as `admin`/`admin123`. | `config.py:45-47,119-127`; `.env.example:6` ships the same default secret | Generate a random secret and admin password on first run; force a password change |
| S9 | **Pairing PIN written to logs** | Anyone who can read the hub logs or console can pair a device | `device_manager/manager.py:64` | Show it only in the authenticated UI |

### Potential risks (Likely / not exploited)

| # | Concern | Evidence | Remediation |
|---|---|---|---|
| R1 | No TLS. Tokens travel in `?token=` URL query strings over plain HTTP/WS and may show up in access logs | `media_transport.dart:59-61`, `control_client.dart:33-35`, `AndroidManifest.xml usesCleartextTraffic="true"` | TLS with a pinned self-signed certificate, tokens in headers |
| R2 | Phone stores its token in plain `SharedPreferences` | `credential_store.dart:57-61` | `flutter_secure_storage` / Android Keystore |
| R3 | Web token in `localStorage` (readable by any XSS). The dashboard builds HTML with template strings, e.g. device names in `main.py:309,325` and component files | `api.js:351,371` | `textContent`/escaping; HttpOnly cookie |
| R4 | Device token check is O(n) HMAC over all devices on every call | `manager.py:169-183` | Index by a token prefix/ID |
| R5 | Session tokens are not checked against a still-active user | `tokens.py:78-133` | Check `users.is_active` |
| R6 | Release APK signed with the debug key | `android/app/build.gradle.kts:28-33` | Release keystore |
| R7 | Video and recordings stored unencrypted on disk | `recorder.py` writes MP4 to `recordings/` | Optional encryption at rest; document it |

### Privacy positives (Verified)
- No mandatory cloud calls. The only outbound target is an optional local Ollama at `127.0.0.1`.
- No secrets committed: no `.env` file in the repo; `.gitignore` excludes `.env`, `*.db`, `recordings/`, `snapshots/`. The default HMAC string in `config.py`/`.env.example` is a public placeholder, not a real secret, but it is accepted at runtime (S8).
- Passwords use PBKDF2 with salt (`auth/passwords.py`). Device tokens are stored as HMAC hashes. Restore is limited to `BACKUP_DIR`.

---

## 10. Performance and Reliability Findings

All items are **risks found by reading the code, not measured**, unless marked otherwise.

| Area | Finding | Evidence |
|---|---|---|
| Video ingest | H.264 decoding and SQLite writes run synchronously inside the async WebSocket handler, on the server's single event loop. A busy stream can stall every HTTP request and other cameras. | `routes/streams.py:56` → `server.py:62-96` → `decoder.py:79-113` |
| Memory | Pre-event buffer ≈ 830 MB per camera (raw BGR); up to 4 cameras ≈ 3.3 GB | `recorder.py:129`, `recorder.py:51` (`frame.copy()`) |
| Live preview CPU | Every viewer re-encodes a JPEG (with overlay) about 30 times a second per camera; the `overlay` query parameter the UI sends is ignored | `routes/streams.py:86-105`, `live_view.js:50,100` |
| Phone | MediaCodec runs on the Android main thread with 10 ms blocking waits per frame; each frame is copied Dart → Kotlin | `MainActivity.kt:22-55,97,108` |
| Phone lifecycle | Streaming stops whenever the app is backgrounded or the screen turns off; no foreground service | `camera_screen.dart:53-73` |
| Reconnect | Backoff exists on the phone, but reconnect always fails auth (§8.2). Media transport gives up after 10 attempts (`failed` state with no retry button). Control client retries every 3 s forever. | `media_transport.dart:104-108`, `control_client.dart:88-94` |
| Decoder recovery | After a reset the hub waits for a keyframe but never asks for one; the phone ignores `request_idr`. Mitigated by 1-second GOP. | `control.py:45-53`, `camera_screen.dart:138` |
| DB growth | `event_predictions` gets a row about every 0.8 s per streaming camera, with no retention | `engine.py:549`, `retention.py` |
| Shutdown | Event engine / AI threads are daemon threads joined with 1 s timeouts; in-flight clip writes may be cut off | `pipeline.py:105-109` |
| Multi-camera | One AI worker thread round-robins all cameras; `MAX_CONCURRENT_CAMERAS=4` is defined but never enforced (not found in `stream_engine`) | `pipeline.py:111-165`, `config.py:62` |
| AI inference speed (measured) | Placeholder detector ~4–5 ms/frame on CPU; SpectatorNet loads on CPU. These numbers say nothing about real YOLOv8n speed. | Audit command, §11 |

---

## 11. Testing Report

| Check | Command | Result | Notes |
|---|---|---|---|
| Python test suite | `SMART_SPECTATOR_ENV=test PYTHONPATH=. DATABASE_PATH=<scratch> … python3 -m pytest tests/ -q` | **176 passed**, 0 failed (12 s) | Run with DB and media paths redirected to a scratch folder; the local `smart_spectator.db` was not modified |
| Flutter static analysis | `flutter analyze --no-pub` (Flutter 3.47.8) | **No issues found** | — |
| Flutter tests | `flutter test --no-pub` | **1 passed** | The only test checks the root widget builds; no logic is tested |
| flake8 (CI selection) | `python3 -m flake8 . --select=E9,F63,F7,F82 --exclude=apps/camera,.git` | **2 errors**: F821 undefined name `Any` | `services/device_manager/discovery.py:38-39`. Harmless at runtime, but fails the CI lint step |
| Bandit (CI) | `bandit -r services/ shared/ …` | **Not run** | Bandit is not installed; not installed per audit rules |
| JS syntax | `node --check` on every `apps/client/js/**/*.js` | **Pass** | Syntax only; no frontend tests exist |
| Route auth inventory | Script listing every FastAPI route and its auth dependencies | ~40 open routes | See §9 |
| Pairing / token / auth behaviour | Script using `TestClient` against a scratch DB (no lifespan, so no mDNS/ports opened) | Reproduced §8.1, 8.2, 8.4–8.6 and S1–S6, S8 | — |
| Model load | ONNX Runtime CPU load of `yolov8n.onnx`, `detector_v1.onnx`, `spectatornet.onnx` | All load | `detector_v1.onnx.data` and `yolov8n.onnx.data` have **different SHA-256** (release uses older weights file via symlink) |
| Detector behaviour | `YOLOObjectDetector.detect()` on black / white / noise frames | `person 0.88` each time | Proves the placeholder |
| Android build | `flutter build apk` | **Not run** | Long Gradle build and dependency downloads; an older debug APK exists (15 Oct) |
| CI workflow | Read `.github/workflows/ci.yml` | **Likely failing** | flake8 errors; `flutter-version: "3.24.x"` cannot satisfy `sdk: ^3.12.0` in `pubspec.yaml`; `libgl1-mesa-glx` is not available on current `ubuntu-latest` images (Likely) |
| End-to-end phone → hub | — | **Not run** | No Android device available |
| QNN / Snapdragon | — | **Not run** | No hardware |

**Important missing tests**
- An end-to-end test of the *app's* pairing sequence (request, then verify) against the real API. The existing tests call the endpoints in the "correct" order, so they miss §8.1.
- A test that a device can reconnect after its control socket closes (§8.2).
- A test asserting `ai_pipeline.detector.is_loaded` after startup, plus a "blank frame → no detections" model sanity test.
- A test that every non-public route rejects anonymous requests (would have caught S1–S4).
- Frontend tests of any kind; Dart unit tests for `PacketEncoder`, `MediaTransport`, and YUV conversion.

---

## 12. Deployment Readiness

**If a developer cloned GitHub today:** `requirements.txt`, the auth package and the encoder bridge **are not on GitHub** (§2). The hub at `origin/main` is a different, older system from the one audited here.

**If a developer used this laptop's working tree:**

| Step | Outcome |
|---|---|
| `pip install -r requirements.txt`, `scripts/start_dev.sh` | Hub starts; DB created; dashboard at `http://<ip>:8000/` (Likely; the lifespan was not run during the audit to avoid opening network ports, but every module imports and the tests pass) |
| Open dashboard | Live preview area loads. Devices, events, recordings, rules and zones fail with 401; there is no way to log in. |
| Install app (`flutter run` on Android) | Builds per `flutter analyze` (not built in this audit) |
| Pair phone | Fails (§8.1). Workaround: the operator reads the PIN from the hub console and calls `/pair/verify` manually. |
| Stream | Possible once paired, but stops working after the first disconnect (§8.2); picture quality on a real phone unverified (§8.8) |
| AI / events | Nothing is detected (detector not loaded). If it were loaded, every frame would contain a fake "person". |
| Snapdragon / QNN | Requires `onnxruntime-qnn` and a Snapdragon PC. Neither is in `requirements.txt`. Unverified. |
| Python version | `requirements.txt` says ≥3.10,<3.14; this machine runs 3.13. PyAV and OpenCV each ship their own `libavdevice`, which triggers an Objective-C duplicate-class warning on macOS (seen in every run). |
| Windows service | `scripts/install_windows.ps1` exists; unverified |

**Remaining for a real deployment:** everything in P0/P1 below, TLS, a release keystore, a first-run admin password, a documented model download/export step, and an install guide that matches the code.

---

## 13. Recommended Fixes, in Priority Order

| Priority | Problem | Affected Component | Recommended Fix | Dependencies |
|---|---|---|---|---|
| **P0** | ~4,000 lines (auth, requirements, encoder bridge) uncommitted; 37 commits unpushed. One disk failure loses the security layer. | Repository | Review, commit and push to a branch | None |
| **P0** | Phone pairing cannot succeed | `pairing_screen.dart`, `device_manager/manager.py` | Separate request and verify in the UI; do not replace an unexpired PIN | None |
| **P0** | Device token rejected after the first disconnect | `websocket/control.py`, `device_manager/manager.py` | Authenticate on `auth_token_hash IS NOT NULL AND status != 'revoked'`; track connection state in a separate column | None |
| **P0** | Live video, camera control and event data readable/changeable without login (S1–S4) | Hub routes | Default-deny: put `require_viewer` on routers; operator for mutations; token check on events WS; signed media URLs | Dashboard login (P1) so the UI keeps working |
| **P0** | Detector is a placeholder and is never loaded | `ai/models`, `main.py` | Export real YOLOv8n; load at startup; fail health check if not loaded; add a sanity test | None |
| **P1** | Dashboard has no login; wrong token field | `apps/client` | Login view, `access_token`, 401 → login redirect | Auth lockdown (P0) |
| **P1** | Device token outranks viewer; any device can stream as any camera (S5, S6) | `auth/roles.py`, `routes/streams.py` | Separate device permissions; bind `camera_id` to the device | — |
| **P1** | Default admin password / secret accepted by default (S8) | `config.py` | Random secret and first-run password setup; make "development" opt-in | — |
| **P1** | Phone YUV conversion and fixed encoder size | `h264_encoder.dart`, `MainActivity.kt` | Proper NV12/I420 packing using strides, or Surface-input encoding (CameraX → MediaCodec), size from the actual camera | Real Android device for testing |
| **P1** | Decode on the event loop | `routes/streams.py`, `stream_engine` | Move decoding to a per-camera worker thread/queue | — |
| **P1** | Revoke endpoint crashes | `routes/devices.py:97-99` | Use `remove_session`; close the WebSocket | — |
| **P1** | Hub → phone commands missing (IDR, start/stop) | Phone control client, `routes/cameras.py` | Implement command handling; make camera endpoints send commands | Token fix |
| **P2** | SpectatorNet trained only on synthetic data; contradictory metrics | `ai/` | Collect and label real sequences from real detections; retrain; one evaluation script | Real detector |
| **P2** | Pre-roll buffer memory and length; `mp4v` clips | `recorder.py` | Buffer encoded H.264 packets (~15 s); write H.264 MP4 or remux | — |
| **P2** | TCP :8554 dead path | `stream_engine/server.py` | Delete, or finish with auth and forwarding | — |
| **P2** | Retention not scheduled; `event_predictions` unbounded | `storage/retention.py` | Periodic job covering all growing tables | — |
| **P2** | No TLS; tokens in URLs; tokens in plain storage | App + hub | WSS/HTTPS with a pinned cert; `flutter_secure_storage`; headers instead of query strings | — |
| **P2** | CI broken (flake8, Flutter version, apt package) | `.github/workflows/ci.yml`, `discovery.py` | Import `Any`; bump Flutter; fix apt packages | — |
| **P2** | Missing tests listed in §11 | `tests/`, `apps/camera/test` | Add them | Respective fixes |
| **P2** | Android foreground service; mDNS discovery in app | `apps/camera` | Implement | — |
| **P3** | README / earlier audit overstate completion | `README.md`, `docs/` | Rewrite status sections to match this audit | — |
| **P3** | Fake device metadata and hard-coded telemetry | `pairing_client.dart`, `control_client.dart` | Use `device_info_plus`; real encoder FPS | — |
| **P3** | Unused inline dashboard in `main.py` | `main.py:146-366` | Remove | — |
| **P3** | `release` build signed with the debug key | `build.gradle.kts` | Release signing config | — |

**Why these levels.**
- The P0 items either make the core product impossible (no pairing, no reconnect, no real detection), expose camera video to anyone on the network, or put un-backed-up work at risk.
- The P1 items stop normal operation or trust (no operator UI, wrong permissions, likely corrupt video).
- The P2 items are quality, scale and maintainability work that only matters once the main path works.

---

## 14. Suggested Implementation Roadmap

### Stage 1 — Critical blockers
- **Tasks:** commit/push local work; fix PIN flow; fix token-after-disconnect; bind `camera_id` to device; fix revoke crash; default-deny auth on all non-public routes and the events WebSocket.
- **Components:** repo, `device_manager`, `routes/*`, `websocket/*`, `apps/camera/lib/features/pairing`.
- **Done when:** a test pairs a device using the app's exact call order, disconnects, reconnects and streams again. A test confirms every non-public route returns 401 without a token.

### Stage 2 — Core integrations
- **Tasks:** dashboard login + token handling + authenticated media URLs; real YOLOv8n export loaded at startup; YUV/encoder fix; hub → phone command channel (IDR, start/stop); move decoding off the event loop.
- **Components:** `apps/client`, `ai/models`, `main.py`, `apps/camera`, `stream_engine`.
- **Dependencies:** Stage 1 auth.
- **Done when:** on a real Android phone on the same Wi-Fi, an operator logs into the dashboard, pairs the phone, sees correct-colour live video, and sees detections of a real person (and none on an empty room) in the overlay.

### Stage 3 — Functional completion
- **Tasks:** encoded-packet pre-roll (~15 s) and H.264 MP4 clips; periodic retention; mDNS discovery in the app; Android foreground service; collect real sequences and retrain/evaluate SpectatorNet; decide whether TCP :8554 stays.
- **Done when:** a real event (e.g. a person loitering in a zone) produces exactly one event row, a playable clip in the browser with ~15 s before the event, and a live dashboard notification.

### Stage 4 — Reliability and security
- **Tasks:** TLS/WSS with a pinned certificate; secure token storage on the phone; random secrets and first-run admin setup; separate device permissions; enforce camera limits; memory caps; release signing.
- **Done when:** a fresh install has no default credentials, all traffic is encrypted, and a 2-hour, 4-camera soak test keeps hub memory steady (measured).

### Stage 5 — Final validation
- **Tasks:** green CI (lint, bandit, pytest, Flutter); Dart unit tests and frontend smoke tests; Snapdragon/QNN benchmark on real hardware; Windows install test; update the README to match reality.
- **Done when:** CI passes on GitHub; a new developer follows the README from a fresh clone to a working phone → hub → dashboard event without outside help.

---

## 15. Final Readiness Assessment

| Area | Status | One-line reason |
|---|---|---|
| Overall functional completeness | **Incomplete** | Many parts exist, but the core path (pair → stream → detect → event) does not work end to end |
| Mobile app (Android) | **Blocked** | Cannot pair; cannot reconnect; video correctness unverified on a device |
| Mobile app (iOS) | **Missing** | No iOS code |
| Web application | **Blocked** | No login, so most pages cannot load data |
| Backend | **Needs improvement** | Solid structure and tests; auth gaps, event-loop blocking, several broken endpoints |
| AI pipeline | **Blocked** | Detector is a placeholder and is never loaded; SpectatorNet has no real training data |
| Integration | **Blocked** | Breaks at pairing, reconnect, detector, and dashboard auth |
| Security & privacy | **Needs improvement** (currently unsafe on a shared LAN) | Video and controls open to the network; weak defaults; no TLS. Local-only design itself is real. |
| Deployment | **Incomplete** | Key files not on GitHub; no model setup step; Windows/QNN unverified |
| Testing | **Needs improvement** | 176 unit tests pass but miss the real integration failures; CI likely red; almost no Dart or JS tests |

### What must be fixed before Smart Spectator can work as one complete, integrated application?

1. **Save the work.** Commit and push the uncommitted auth system, `requirements.txt`, and encoder code.
2. **Make a phone able to connect and stay connected.** Fix the PIN flow and the "token dies after disconnect" bug, and tie each token to its own camera.
3. **Give the AI real eyes.** Replace the placeholder `yolov8n.onnx` with the real YOLOv8n and load it when the hub starts.
4. **Let operators in, and keep everyone else out.** Add dashboard login, and require authentication on live video, camera controls, event data and the events WebSocket.
5. **Prove the phone's video is correct on a real Android device.** Fix YUV conversion, encoder sizing, and hub → phone commands.

Once these five are done, the existing event engine, recording, rules and dashboard code (which is the most mature part of the repository) can finally receive real data. Training SpectatorNet on real recordings is the next step after that.

---

*Report generated by an audit-only pass. No application code, configuration, dependencies, models or database files were changed. The local `smart_spectator.db` was not modified (checked by file modification time), and `git status` was identical before and after all checks.*
