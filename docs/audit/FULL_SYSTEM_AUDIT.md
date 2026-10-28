# Smart Spectator — System Audit Against the Phone + xAI Vision

**Date:** 28 October 2026
**Repository:** `krishna-gera/smart-spectator`, branch `main` @ `4467eb2` plus uncommitted work (see §1)
**Previous audit (PC-hub design):** [`FULL_SYSTEM_AUDIT_2026-10-28_pc-hub.md`](FULL_SYSTEM_AUDIT_2026-10-28_pc-hub.md). It has the detailed bug evidence referenced below.

**Target design (from the product owner):**
- Secondary phones run in **Camcorder Mode**.
- The main phone runs in **View Mode**.
- A **web dashboard** sits alongside them.
- **All AI goes through the xAI API.** No local models, no training, no YOLO/YOLOX/ByteTrack/SpectatorNet.
- There is **no dedicated PC**.

Labels: **Verified** = proven by code, docs or a command run during the audit. **Likely** = strongly indicated. **Unverified** = could not be established.

---

## 0. Summary in one minute

- **Reusable:** the Android camera app, which already captures, H.264-encodes and streams over Wi-Fi. Also the binary packet protocol, the pairing/token *design*, and the web dashboard's look and pages.
- **Built for the removed PC:** the whole Python/FastAPI hub in `services/`. It cannot run on a phone. Its logic (pairing, rules, zones, event states) is useful as a specification to re-implement in the phone app.
- **Must be retired:** all local AI. That is `ai/`, `services/ai_engine/`, 10 model files (~39 MB), training/benchmark scripts and `artifacts/`: about 7,350 lines of Python.
- **Missing:**
  - Any xAI integration (zero references in the codebase, Verified).
  - A **View Mode** in the phone app.
  - A way for the main phone to *receive and show* video.
  - A secure place to keep the xAI key.
- **Feasibility of the xAI flow:** **feasible with changes.**
  - xAI accepts **still images only** (JPEG/PNG, ≤ 20 MiB), with no video input (Verified, docs.x.ai).
  - So the main phone must send **selected snapshots**, not video.
  - Sending every frame is far too slow and expensive. A cheap **non-AI motion check** (pixel difference) must decide *when* to send a snapshot.
- **Key rule conflict:** "No PC" and "keep the API key on a backend" together mean you need a **small hosted proxy** (a serverless function). This is the only cloud piece, and it only carries AI requests.
- **Biggest privacy point:** every AI analysis sends a camera image off the home network to xAI. This must be opt-in, visible to the user, and limited.

---

## 1. GitHub and working-tree status

| Item | Result |
|---|---|
| Fetch | `git fetch --all --prune` succeeded |
| Local vs GitHub | 37 commits **ahead**, 0 behind. Nothing to pull, so no pull was run. |
| Uncommitted work | 98 changed/untracked paths (≈ +4,063 / −786 lines), including all auth code, `requirements.txt` and the phone encoder bridge |
| Safety backup made | `backups/uncommitted-2026-10-28/` (git-ignored): `working_tree_vs_HEAD.patch` (checked: reverse-applies cleanly), `staged.patch`, `status.txt`, `untracked_files.tgz` |
| Commits / pushes | **None.** Waiting for your approval. |

---

## 2. What can be reused

| Component | Path | Reuse as | Notes |
|---|---|---|---|
| Camera capture + hardware H.264 encode | `apps/camera/lib/features/camera/camera_screen.dart`, `apps/camera/lib/core/codec/h264_encoder.dart`, `apps/camera/android/.../MainActivity.kt` | **Camcorder Mode, directly** | Known defects to fix: YUV plane copying ignores strides (`h264_encoder.dart:23-35`); a possible endless loop at `MainActivity.kt:111`; encoder runs on the UI thread |
| Packet protocol (24-byte header + H.264) | `apps/camera/lib/core/protocol/packet_encoder.dart`, `docs/05_CAMERA_PROTOCOL.md` | **Camcorder → main phone link, directly** | Needs a Dart *decoder* on the main phone (only the Python one exists: `services/stream_engine/protocol.py`) |
| Media and control transports | `apps/camera/lib/core/streaming/media_transport.dart`, `apps/camera/lib/core/control/control_client.dart` | **Directly** | Reconnect backoff exists; incoming commands are ignored (`media_transport.dart:71-73`) |
| Pairing client + credential store | `apps/camera/lib/core/pairing/`, `apps/camera/lib/core/storage/credential_store.dart` | **With fixes** | The current tap flow regenerates the PIN every time, so pairing always fails (Verified in the previous audit). The token is stored in plain SharedPreferences. |
| Hub discovery | `apps/camera/lib/core/discovery/hub_discovery.dart` | **Partly** | Probes 8 guessed IPs. Should become mDNS (`multicast_dns`, already in the local pub cache) or a QR code shown by the main phone. |
| Pairing / token / RBAC design | `services/device_manager/*.py`, `services/hub_backend/auth/*.py` | **Spec only** (port to Dart) | Good ideas: PIN with expiry and attempt limits, HMAC-hashed tokens, roles. Bug to avoid: token rejected after disconnect (`websocket/control.py:28-32` + `manager.py:170-171`). |
| Event logic (debounce, cooldown, state machine, severity, rules, zones) | `services/event_engine/{debouncer,cooldown,state_machine,severity,rules,zones}.py` | **Spec only** (port to Dart) | Model-agnostic and well tested (176 Python tests pass). It can consume xAI results instead of SpectatorNet output. |
| Web dashboard UI | `apps/client/` (vanilla JS, no build step) | **Re-point** | Pages for devices, events, recordings, zones, rules, settings. It has no login (Verified) and calls a FastAPI hub that will not exist. |
| Data schema ideas | `services/hub_backend/database/schema.py` | **Spec only** | Re-create a smaller set with `sqflite` on the main phone (already in the local pub cache) |

---

## 3. Built around the removed PC hub

| Component | Path | Why it doesn't fit | Recommendation |
|---|---|---|---|
| FastAPI hub (≈100 routes) | `services/hub_backend/` | A Python server process; cannot run inside an Android app | Freeze as reference. Remove after the phone hub reaches parity. |
| Stream engine (PyAV decode) | `services/stream_engine/` | PC decoding; the main phone must use Android `MediaCodec` instead | Reference only |
| mDNS advertiser | `services/device_manager/discovery.py` | Advertises the PC | Re-implement on the main phone |
| PC start scripts / Windows service | `scripts/start_dev.sh`, `scripts/start_production.sh`, `scripts/*_windows.ps1` | PC deployment | Retire |
| Snapdragon / QNN docs and validation | `docs/12_SNAPDRAGON_OPTIMIZATION.md`, `docs/SNAPDRAGON_*.md`, `scripts/validate_snapdragon_runtime.py`, `artifacts/phase8/*` | Hardware no longer in scope | Archive |
| Python dependencies | `requirements.txt` (fastapi, av, opencv, onnxruntime, zeroconf…) | PC runtime | Only the xAI proxy will need server code, and it should be tiny |
| CI job "Snapdragon ARM64 & QNN" | `.github/workflows/ci.yml` | No longer relevant | Remove; add a Flutter test job with a current Flutter version |
| The app's name/role | `apps/camera` (`smart_spectator_camera`) | Assumes the phone is only a camera | Turn into one app with two modes |

---

## 4. Local AI that is now unnecessary

All of these contradict "no local models, no training" (Verified file list via `git ls-files`):

- **Code:**
  - `ai/training/`, `ai/models/*.py`, `ai/inference/`, `ai/monitoring/`, `ai/evaluation/`, `ai/datasets/`
  - `services/ai_engine/` (detector, ByteTrack tracker, frame sampler, visualizer)
  - `scripts/export_*`, `scripts/benchmark_*`, `scripts/evaluate_*`, `scripts/validate_*onnx*`, `scripts/generate_synthetic_dataset.py`
  - About **7,350 lines of Python** in total.
- **Model files tracked in git (~39 MB):** `ai/models/yolov8n.onnx(.data)`, `spectatornet.onnx/.pt/_int8.onnx`, and copies in `ai/models/releases/`.
  - Note: the "YOLOv8n" file was a random-weight placeholder anyway. It reports "person 0.88" on a black frame (Verified in the previous audit).
- **Local LLM adapter:** `ai/orchestration/llm_adapter.py` (Ollama on `127.0.0.1:11434`). Replace it with the xAI integration.
- **Evaluation/benchmark outputs:** `artifacts/` (1.3 MB).
- **Event engine links to SpectatorNet:** `services/event_engine/service.py:12,31-60`.
- **Tests that exist only for local AI:**
  - `tests/test_ai_pipeline.py`
  - `tests/test_phase3_spectatornet.py`
  - `tests/test_phase7_snapdragon_inference.py`
  - `tests/test_phase8_model_integrity.py`
  - `tests/test_phase9_model_registry.py`
  - `tests/test_phase10_model_registry.py`

**Recommendation:** remove these in **one separate, reviewable commit** after you approve it. That lets git history keep the old work.

---

## 5. Missing xAI integration — capabilities checked

| Fact | Status | Source |
|---|---|---|
| Image understanding via `POST https://api.x.ai/v1/responses`, image as base64 data URL or public URL | **Verified** | docs.x.ai image-understanding guide |
| Formats: **JPEG and PNG only**; max **20 MiB** per image; no stated per-request image limit | **Verified** | same |
| **No video input** on any model; "video" models only *generate* video | **Verified** | docs.x.ai models page |
| Billing is per token, including "image tokens"; no published tokens-per-image figure | **Verified** (figure unknown) | docs.x.ai pricing |
| Current text+vision model examples use `grok-4.7` ($2 / $6 per 1M input/output tokens) | **Verified** | models page |
| Rate limits (RPM/TPM) | **Unverified.** The pages only say "per-minute limits apply". | pricing page |
| Data retention / use of API images for training / zero-retention option | **Unverified.** The public legal FAQ returned HTTP 403. | must be checked in your xAI account terms |
| Reasoning models can be slow; docs suggest very long client timeouts | **Verified** | image-understanding guide |

### What this means for each AI feature

| Feature idea | Feasible? | How |
|---|---|---|
| "What is happening in this camera right now?" | **Yes** | Send one JPEG snapshot with a prompt |
| Event classification (person, package, open door, fire/smoke, unusual activity) | **Yes, per snapshot** | Ask for a strict JSON answer (category, confidence, short description). Validate it in code. |
| Continuous real-time detection / tracking at video rate | **No** | No video input; per-request latency and cost are too high. Use a motion trigger plus occasional snapshots. |
| Understanding a short action ("someone picked up a box") | **Partial** | Send 2–4 snapshots in time order in one request (multi-image is allowed). Accuracy is unverified and must be tested. |
| Works with no internet | **No** | All AI is remote. Show "AI offline" and keep recording/motion alerts working. |

### Cost and volume (example arithmetic, not measured)
Sending one snapshot every 2 seconds from one camera means **43,200 requests per day**. That is why AI calls must be triggered by motion, rate-limited per camera (for example at most one call every 30–60 s per camera, plus manual "analyze now"), and capped per day.

---

## 6. Tracing the intended workflow

`Camera Phones → Local Network → Main Phone → Secure API Integration → xAI API → AI Results → Notifications and Mobile/Web Interfaces`

| Step | Status today | Problem | What to build |
|---|---|---|---|
| Camera phone captures + encodes | **PARTIAL** | Works in code; YUV handling likely wrong on real phones; untested on a device | Fix the conversion; test on a phone |
| Local network → main phone | **MISSING** | Camera phones only know how to talk to the PC hub's endpoints. No phone can *receive* a stream. | A **LAN server inside the main phone's app** (Dart `dart:io` HttpServer + WebSockets). Keep the same paths and packet format so the camera code barely changes. |
| Pairing camera ↔ main phone | **BROKEN** (Verified) | PIN regenerated on every tap; token dies after disconnect | Re-implement pairing on the main phone with both bugs fixed; show the PIN on the main phone's screen |
| Main phone shows live video | **MISSING** | No decoder or viewer in the app | Android `MediaCodec` decoder rendering to a Flutter `Texture` (platform channel) |
| Snapshot selection (when to ask AI) | **MISSING** | Motion gating existed only inside the retired Python AI pipeline | Simple frame-difference motion check, which is not an AI model. Running it on the camera phone saves battery and bandwidth on the main phone. |
| Secure API integration | **MISSING** | No key handling anywhere | **Hosted proxy** (see §7) that holds the xAI key, checks the caller, enforces rate limits and budgets, and forwards the image |
| xAI analysis | **MISSING** | No client | Proxy calls `/v1/responses` with `store: false` and a strict JSON prompt |
| AI results → events | **MISSING** | Event logic exists only in Python | Port debounce/cooldown/severity/state machine to Dart; store events in `sqflite` on the main phone |
| Notifications | **MISSING** | Python only pushed to a browser WebSocket | Local Android notifications on the main phone (`flutter_local_notifications`) |
| Web dashboard | **DISCONNECTED** | Points to a FastAPI hub that won't exist; no login | Serve the dashboard **from the main phone** on the LAN (same embedded server), with login |

### How the web app talks to the main phone

- **Recommended for v1 (same Wi-Fi):** the main phone serves the dashboard and a small REST/WebSocket API at `http://<main-phone-ip>:8000`. Live view uses MJPEG or snapshots produced by the main phone. This works only while the main phone app is open/running and on the same network. The dashboard must say this clearly.
- **Later (away from home):** needs a cloud relay. The hosted proxy could also store *event summaries and snapshots* so the dashboard can show history remotely. Remote *live video* needs WebRTC plus a TURN server, a much bigger project. Not recommended for v1.

### When the main phone is unavailable

| Situation | Behaviour to build |
|---|---|
| Main phone off / app killed / different network | Camera phones show "Main phone not reachable" and retry with backoff (already coded). They should keep a short local recording buffer and run the motion check, then report "motion while offline" when the link returns. |
| Main phone online but no internet | Live view, recording, motion alerts and device management keep working. **AI analysis pauses** and the UI shows "AI offline". Optionally queue a few snapshots to analyse later (the user chooses). |
| Web dashboard while main phone is off | Shows "Main phone offline". Nothing to view in v1 (no cloud copy). |
| Android kills the main phone's server in the background | A foreground service with a persistent notification is required; without it, Android will stop the server (Likely, standard Android behaviour) |

---

## 7. Recommended architecture

```
CAMERA PHONES (Camcorder Mode)                       MAIN PHONE (View Mode)
  capture → H.264 encode → SS packets  ──Wi-Fi WS──►  Embedded LAN server (Dart)
  motion check (pixel diff, no AI)                     ├─ pairing + device tokens
  control socket (status, commands) ◄──────────────►   ├─ stream registry + MediaCodec decode → live tiles
                                                       ├─ snapshot picker (motion + rate limit)
                                                       ├─ event logic (Dart port) + sqflite
                                                       ├─ local notifications
                                                       └─ serves web dashboard on LAN  ◄── browser (same Wi-Fi)
                                                                │ HTTPS (snapshot JPEG + app token)
                                                                ▼
                                                  HOSTED AI PROXY (small serverless function)
                                                    holds XAI_API_KEY, auth, per-user rate limit,
                                                    daily budget, strips metadata, no image storage
                                                                │ HTTPS
                                                                ▼
                                                           xAI /v1/responses
```

**Why a hosted proxy and not the phone:** a key inside an APK or browser can be extracted. The product owner's rule is to keep it server-side.

**Options:**
- **(a) Hosted proxy.** Cloudflare Workers, Firebase Cloud Functions, Vercel, etc. Cheap, no PC. **Recommended.**
- **(b) User pastes their own key into the main phone,** kept in the Android Keystore. Acceptable for **development only**, and still against the stated rule for production.

**Offline vs internet**

| Works offline (LAN only) | Needs internet |
|---|---|
| Pairing, live view, recording, motion alerts, device management, web dashboard on LAN, event history | AI analysis/insights (xAI), remote access, cloud backup |

---

## 8. Security, privacy, performance, deployment issues

### Security
1. **No transport encryption.** Everything is `ws://` / `http://`, and the token sits in the URL (`media_transport.dart:59-61`; `AndroidManifest.xml` `usesCleartextTraffic="true"`). On a home LAN this is a moderate risk. Add TLS with a certificate pinned during pairing (Stage 4).
2. **Device token in plain SharedPreferences** (`credential_store.dart:57-61`). Move it to secure storage.
3. **xAI key** must never be in the app or browser. Proxy only. The proxy must authenticate callers, or anyone could spend your quota.
4. **Web dashboard** has no login (Verified previously). The phone-served version needs one from day one.
5. **Release APK** is signed with the debug key (`android/app/build.gradle.kts:28-33`).

### Privacy
1. **Every AI call sends a home camera image to a US company's servers.** Requirements:
   - an explicit per-camera opt-in;
   - an "AI analysis is ON" indicator;
   - a log of what was sent;
   - an option to blur/crop zones before sending (simple image operations, not AI).
2. **xAI retention/training terms are Unverified.** Check your xAI account's data controls before launch and send `store: false` on requests.
3. **Faces, children, neighbours:** sending images of people to a third party may need consent in some places (GDPR-style rules). Get legal advice before a commercial launch.
4. **Positive:** video itself never leaves the LAN; only selected snapshots do.

### Performance
1. The main phone decoding several 720p streams at once: Android hardware decoders usually allow a limited number of simultaneous sessions (Likely 2–4 on mid-range phones; **must be measured**). Recommend 480p/15 fps for camera tiles, with full quality only for the one camera being viewed.
2. Battery/heat on camera phones streaming 24/7: recommend charging, lower bitrate, and a thermal warning (telemetry already sends battery level).
3. xAI latency is seconds, not milliseconds. AI results arrive as "insights" after the fact, not as real-time overlays.

### Deployment
1. One APK with two modes (Android only for now). Release signing is needed.
2. The hosted proxy needs an account, a deployment, and the `XAI_API_KEY` secret. These are your actions.
3. CI must drop the Python/QNN jobs and add Flutter analyze/test with a matching Flutter version (the current CI pins 3.24.x, which can't satisfy the app's `sdk: ^3.12.0`).

---

## 9. Implementation order

| Stage | Goal | Main work | Done when |
|---|---|---|---|
| **1. Local link** | Main phone can pair cameras and receive their streams | Mode selection in one app; Dart LAN server on the main phone (pairing, tokens, ingest, control); fixed pairing UI on the camera; Dart packet decoder; unit + loopback tests | Automated test: a camera client pairs, streams packets, disconnects, reconnects with the same token. Manual: two real phones pair. |
| **2. Live view** | See the cameras on the main phone | MediaCodec decoder → Flutter Texture; multi-camera grid; fix camera YUV/encoder; mDNS/QR discovery; foreground services | Two camera phones show correct live video on the main phone for 30 minutes |
| **3. Events (no AI yet)** | Useful without internet | Motion check; Dart event logic; sqflite history; local notifications; snapshot + short clip saving | Motion in front of a camera gives one notification and one history entry |
| **4. xAI insights** | AI through the API | Hosted proxy (auth, rate limit, budget, `store:false`); snapshot → JSON insight → event enrichment; privacy opt-in and log | A snapshot sent through the proxy returns a validated JSON description; the key never appears in the app |
| **5. Web dashboard** | Browser on the same Wi-Fi | Main phone serves `apps/client` (re-pointed) with login | A laptop browser logs in and sees live tiles and events |
| **6. Harden & clean** | Production readiness | TLS + pinning; secure storage; release signing; retire Python hub and local AI (separate approved commit); CI | CI green; fresh-install checklist passes on real phones |

---

## 10. What needs you

1. **Approve committing** the current uncommitted work (backed up, not committed).
2. **Choose the AI proxy host** (Cloudflare Workers / Firebase / Vercel / other). Create the xAI account/API key and check its data-retention settings.
3. **Approve removing** the local-AI code and PC hub (Stage 6, one commit).
4. **Test on real Android phones** at the end of Stages 1, 2 and 3 (checklists will be provided).
5. **Privacy/legal decision** on sending images of people to xAI before any public release.
