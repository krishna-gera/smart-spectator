# SMART SPECTATOR — ENGINEERING REMEDIATION PLAN

**Date:** October 1, 2026  
**Status:** In Progress — Master Remediation Active  
**Lead Roles:** Principal Software Architect, Senior Backend Engineer, Senior Android Engineer, AI/ML Systems Engineer, DevSecOps Engineer, QA Engineer, Systems Engineer  

---

## 1. Verified Baseline Findings

Following code-level inspection and execution verification, the following baseline findings are established:

### P0 (Critical Blockers)
1. **Android Video Pipeline Disconnected (`apps/camera`):**
   - In `apps/camera/lib/features/camera/camera_screen.dart`, `CameraController` is created for UI preview, but `startImageStream()` is never called.
   - `MediaTransport.sendPacket()` in `apps/camera/lib/core/streaming/media_transport.dart` is never called anywhere in the codebase.
   - `PacketEncoder` (SSP1 24-byte protocol framing) is dead code.
   - Native Android hardware H.264 `MediaCodec` encoding is completely missing; `MainActivity.kt` is an empty `FlutterActivity`.
2. **REST APIs Unauthenticated (`services/hub_backend`):**
   - Zero FastAPI routes in `services/hub_backend/routes/` enforce authentication or check authorization headers.
   - `get_current_device` dependency in `dependencies.py` is defined but unused.
   - Destructive operations (`DELETE /devices/{id}`, `DELETE /recordings/{id}`, `POST /system/restore`, `PUT /system/config/{cat}`) are accessible to any unauthenticated caller on the local network.
3. **Pairing Security Flaw (`services/device_manager`):**
   - `POST /api/v1/devices/pair/request` returns `"verification_code": pin` in the HTTP response body to the calling device, defeating the proximity challenge-response security architecture.
   - `GET /api/v1/devices/pairing/pending` leaks active PINs without authentication.
4. **WebSocket Real-Time Broadcast Failure (`services/hub_backend/websocket`):**
   - `_on_event_engine_broadcast` in `events.py` calls `asyncio.get_running_loop()` from the `EventEngine._worker_thread` OS thread.
   - In non-asyncio OS threads, this raises `RuntimeError: no running event loop`, which is caught and silently swallowed. Zero real-time events reach the web dashboard.
5. **Demo Runner AI Bypass (`scripts/run_demo.py`):**
   - `run_demo.py` instantiates `YOLOObjectDetector` without calling `load()`. `detect()` returns 0 detections and tracker produces 0 tracklets, yet script prints "ALL SYSTEMS NOMINAL".
6. **SpectatorNet Uncalibrated Placeholder (`ai/models`):**
   - Trained for 8 seconds on 180 synthetic JSON files; evaluates to 14% accuracy on synthetic validation (macro F1 0.053; 0.0 precision on 7/9 classes).
   - In `EventEngineService`, SpectatorNet defaults to CPU execution.
   - Published benchmarks in `README.md` were measured on Apple Silicon Mac (`CoreMLExecutionProvider`), not Qualcomm Hexagon NPU.

### P1 (High Risks)
7. **Orphaned Phase 10 Island Modules (`services/event_engine`, `ai/orchestration`):**
   - `incident_engine`, `anomaly_detector`, `context_engine`, `event_relationships`, `memory_manager`, and `ai_orchestrator` are completely disconnected from the live video stream pipeline.
8. **Fake Edge LLM Abstraction (`ai/orchestration/llm_adapter.py`):**
   - `LocalReferenceLLMProvider` is an offline 2-line hardcoded string return (`if "summarize" in prompt: ...`).
9. **Subnet IP Probing Discovery (`apps/camera/lib/core/discovery/hub_discovery.dart`):**
   - Scans 8 hardcoded candidate octets via HTTP GET rather than performing genuine mDNS/DNS-SD discovery.
10. **Silent Exception Swallowing:**
    - `decoder.py` silently swallows PyAV decoding exceptions; `events.py` silently swallows WebSocket broadcast errors.

### P2 (Technical Debt)
11. **Direct SQL Invocations:** Approximately 148 raw SQL queries embedded directly inside route handlers, service classes, and background workers without repository boundaries.
12. **Duplicate Code:** Duplicate storage retention (`recorder.py` vs `retention.py`); duplicate `CameraSource` classes (`shared/protocols/camera_source.py` vs `services/stream_engine/sources/base.py`); duplicate schema DDL in `schema.py` and `migrations.py`.
13. **Inconsistent Congestion Threshold:** `resource_manager.py` tests queue depth >= 8, while `pipeline.py` hardcodes queue maxsize=2.
14. **Deprecated APIs:** Over 120 warnings from deprecated `datetime.utcnow()` across models and services.
15. **Relative Path Drift:** Paths defined relative to current working directory rather than an anchored application root directory.

---

## 2. Dependency Graph & Remediation Sequence

Remediation must proceed from security and foundational contracts outward to the functional video capture and streaming pipeline:

```
[ STEP 1: Re-audit & Plan ]
         │
         ▼
[ STEP 2: Security Lockdown ] ──► [ STEP 3: Pairing Correction ] ──► [ STEP 4: REST Auth + RBAC ]
         │
         ▼
[ STEP 5: Fix WebSocket Architecture (Thread-safe Dispatch) ]
         │
         ▼
[ STEP 6: Fix Demo Runner & Assertions ]
         │
         ▼
[ STEP 7-9: Android Native Capture, MediaCodec H.264 & SSP1 TCP Streaming ]
         │
         ▼
[ STEP 10: Real H.264 PyAV Decoder & Integration Test Fixture ]
         │
         ▼
[ STEP 11-13: Real YOLO Inference, ByteTrack Stabilization & Observation Contracts ]
         │
         ▼
[ STEP 14-16: Event Engine Wiring, Repository Layer & Storage Consolidation ]
         │
         ▼
[ STEP 17-18: Authenticated Dashboard Integration & E2E System Test ]
         │
         ▼
[ STEP 19-20: Orphaned Module Decisions & SpectatorNet Real Dataset Lifecycle ]
         │
         ▼
[ STEP 21-24: CI/CD Hardening, Snapdragon Transparency & Final Audit ]
```

---

## 3. Detailed Phase Action Items & Acceptance Criteria

### Step 2: Security Lockdown
- **Actions:**
  - Create `services/hub_backend/auth/` containing `dependencies.py`, `tokens.py`, `roles.py`, `permissions.py`, `models.py`.
  - Enforce secure token verification using constant-time comparison and indexed/cached lookup.
  - Fail startup if `SMART_SPECTATOR_ENV=production` and `HUB_HMAC_SECRET` is missing or set to default fallback.
  - Make CORS origins strictly configurable via `ALLOWED_ORIGINS` setting (default to local client origins).
- **Acceptance Criteria:**
  - Insecure fallback secret rejected in production mode.
  - Unauthenticated requests to protected endpoints return HTTP 401.

### Step 3: Pairing Correction
- **Actions:**
  - Modify `POST /api/v1/devices/pair/request` to omit `verification_code` / PIN from HTTP response.
  - Expose pending PINs only on the Hub operator interface/console; protect `GET /api/v1/devices/pairing/pending` with Admin/Operator authorization.
  - Add rate limiting and lockouts for consecutive invalid PIN attempts.
- **Acceptance Criteria:**
  - PIN is absent from HTTP response body.
  - PIN is absent from logs (verified by `SensitiveDataFilter`).
  - Brute force attempts locked after 3 failures.

### Step 4: REST Authentication + RBAC
- **Actions:**
  - Define roles: `ADMIN`, `OPERATOR`, `VIEWER`, `DEVICE`.
  - Map every endpoint to an explicit role requirement via `Depends(require_role(...))`.
  - Audit logging records authenticated principal identity instead of hardcoded strings.
- **Acceptance Criteria:**
  - Viewer role cannot delete recordings or modify rules (HTTP 403).
  - Unauthenticated requests receive HTTP 401.

### Step 5: Fix WebSocket Architecture
- **Actions:**
  - Capture main asyncio event loop during FastAPI lifespan startup in `services/hub_backend/main.py`.
  - Update `_on_event_engine_broadcast` in `websocket/events.py` to dispatch coroutines safely using `asyncio.run_coroutine_threadsafe(coro, main_loop)`.
  - Remove silent `except RuntimeError: pass`.
- **Acceptance Criteria:**
  - Triggering an event persists to DB AND immediately delivers JSON payload over `/api/v1/events/stream` to connected WebSocket clients.
  - Integration test verifies event delivery end-to-end.

### Step 6: Fix Demo Runner
- **Actions:**
  - Refactor `scripts/run_demo.py` to explicitly load detector (`detector.load()`), ingest a real sample image (`ai/evaluation/samples/sample_person_phone.jpg`), assert detections > 0, assert tracklets > 0, and fail with non-zero exit code if any stage fails.
- **Acceptance Criteria:**
  - `python scripts/run_demo.py` executes real inference and succeeds only on verified detection.

### Step 7–9: Android Real Camera Capture, MediaCodec & SSP1 TCP Streaming
- **Actions:**
  - In `apps/camera`: Implement native Android capture pipeline (CameraX `ImageAnalysis` / native bridge).
  - Implement hardware H.264 `MediaCodec` encoding producing Annex-B NAL units with SPS/PPS.
  - Encode into 24-byte SSP1 framing with CRC-16.
  - Implement authenticated TCP client streaming to Hub port 8554 (or authenticated WebSocket fallback).
  - Provide an Android Foreground Service with notification for background streaming resilience.
  - Replace candidate IP probing with genuine mDNS client discovery (`_smartspectator._tcp`).
- **Acceptance Criteria:**
  - Real Android phone streams live 720p H.264 video frames over local network to Hub.

### Step 10: Real H.264 Decoder Integration & Test Fixtures
- **Actions:**
  - Create `tests/fixtures/sample_stream.h264` containing valid H.264 Annex-B keyframes and P-frames.
  - Create `tests/integration/test_real_h264_decode.py` testing PyAV decoding into valid BGR numpy arrays.
  - Track decoder telemetry (`frames_decoded`, `decode_errors`, `corrupt_packets`) and eliminate silent exception swallowing.
- **Acceptance Criteria:**
  - Decoder test passes with real H.264 NAL stream producing valid `(720, 1280, 3)` ndarray frames.

### Step 11–13: YOLO Inference, Tracker Stabilization & Observation Contracts
- **Actions:**
  - Formalize detector lifecycle: initialize -> load -> validate -> warmup -> inference.
  - Clarify tracker implementation: retain Hungarian matching with IoU, rename/document state representation transparently, or implement standard Kalman filter state estimation.
  - Enforce `Observation` schema contract across all perception outputs.
- **Acceptance Criteria:**
  - Test verifying real image detection on host execution provider.

### Step 14–16: Event Engine Wiring, Repository Layer & Storage Consolidation
- **Actions:**
  - Ensure data path: `Observation` -> `ZoneEngine` -> `RuleEngine` -> `TemporalDebouncer` -> `ConfirmedEvent` -> DB & WebSocket.
  - Create `infrastructure/repositories/` (`CameraRepository`, `DeviceRepository`, `EventRepository`, `RuleRepository`, `RecordingRepository`) and extract raw SQL from routes.
  - Consolidate `recorder.py` and `retention.py` into a single `StorageRetentionService`.
- **Acceptance Criteria:**
  - Zero `conn.execute()` calls inside API route handlers.
  - Unified retention policy enforcement.

### Step 17–18: Authenticated Dashboard Integration & E2E System Test
- **Actions:**
  - Update `apps/client/js/api.js` and `ws.js` to store auth tokens and transmit `Authorization: Bearer <token>`.
  - Provide operator login/token entry in the web UI.
  - Create simulated camera client streaming real H.264 to verify complete vertical slice in CI.
- **Acceptance Criteria:**
  - End-to-end simulated camera streaming generates live video preview, bounding boxes, events, MP4 clips, and real-time dashboard updates.

### Step 19–20: Orphaned Module Decisions & SpectatorNet Real Dataset Lifecycle
- **Actions:**
  - Relocate unintegrated Phase 10 modules (`incident_engine`, `anomaly`, `context`, `memory`, `ai_orchestrator`) under `services/event_engine/experimental/` with explicit disclaimers.
  - Rename `LocalReferenceLLMProvider` to `DeterministicTemplateSynthesizer`.
  - Document formal model lifecycle and mark SpectatorNet as experimental prototype pending real dataset curation.
- **Acceptance Criteria:**
  - Codebase accurately reflects production vs experimental boundaries.

### Step 21–24: CI/CD Hardening, Snapdragon Transparency & Final Audit
- **Actions:**
  - Update `.github/workflows/ci.yml` with linting, typing, pytest, security scanning (`bandit`), and Flutter analysis.
  - Reconcile documentation across `docs/` to eliminate false claims.
  - Produce comprehensive `docs/FINAL_ENGINEERING_AUDIT.md`.
- **Acceptance Criteria:**
  - All automated checks and tests pass.
  - Complete engineering audit documented and committed.
