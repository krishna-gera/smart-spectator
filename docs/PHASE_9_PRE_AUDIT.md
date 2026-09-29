# Smart Spectator — Phase 9 Pre-Audit Report

**Document ID:** SS-DOC-034  
**Date:** 2026-09-30  
**Repository State:** Version 1.1.0 (Git Tag: `v1.1.0`), Clean Working Tree  
**Automated Tests:** 100/100 tests passing  

---

## 1. Executive Summary & Audit Verification

Prior to commencing Phase 9 engineering, a comprehensive repository audit was executed:
- `git status`: Working tree clean, 28 commits ahead of initial fork.
- `git log --oneline -n 20`: Latest commit `19a7c18 (HEAD -> main, tag: v1.1.0) release: Smart Spectator 1.1.0`.
- `PYTHONPATH=. pytest -q`: 100 passed, 116 deprecation warnings (primarily datetime.utcnow), 0 failures in 9.69s.

---

## 2. Current Architecture Overview

Smart Spectator operates as a local-first, hub-and-spoke visual intelligence mesh:
- **Android Camera Node (`apps/camera`):** Flutter 3.19+ app utilizing CameraX and MediaCodec for hardware H.264 encoding. Communicates via mDNS (`_smartspectator._tcp.local.`) for pairing and a custom binary protocol (`0x53530001` + CRC32) over TCP port 8554.
- **Desktop Hub (`services/hub_backend`):** FastAPI asynchronous web server binding port 8000. Houses SQLite database in Write-Ahead Logging (WAL) mode, REST routing, WebSocket broadcasting, and service lifecycles.
- **Stream Ingestion Engine (`services/stream_engine`):** Dedicated non-blocking TCP socket server on port 8554, packet framing/reassembly, and PyAV / FFmpeg H.264 decoding into BGR NumPy arrays.
- **AI Perception Pipeline (`services/ai_engine`):**
  - Level 1: YOLOv8n spatial detector (ONNX, 640x640) executed via ONNX Runtime with execution provider hierarchy (`QNNExecutionProvider` -> `DmlExecutionProvider` -> `CoreMLExecutionProvider` -> `CPUExecutionProvider`).
  - Level 2: ByteTrack multi-object tracker maintaining Kalman filter states isolated per camera context.
  - Frame Sampler: Adaptive motion gating skipping redundant static frames.
- **Temporal Event Engine (`services/event_engine`):**
  - Level 3: SpectatorNet custom 2-layer GRU evaluating a 16-frame sliding observation window into 6 behavioral classes.
  - Spatial Ray-Casting: Evaluates point-in-polygon containment against defined zones.
  - Recording Manager: Maintains in-memory circular ring buffer (5s pre-roll) and encodes MP4 video clips upon event trigger.
- **Monitoring Client (`apps/client`):** Vanilla HTML5/CSS/JavaScript single-page application served via FastAPI static mount at `/client`.

---

## 3. Current REST & WebSocket APIs

All REST endpoints reside under `/api/v1/`:
- **Health & Diagnostics:**
  - `GET /health` — Basic uptime and health state.
  - `GET /health/detailed` — Component statuses, disk usage, active sessions.
  - `GET /health/components` — Status of decoupled engines.
  - `GET /system/diagnostics` — Unified 11-subsystem health diagnostics.
  - `GET /system/hardware` — Real host silicon and accelerator introspection.
  - `GET /system/metrics` — Telemetry metrics (AI, events, stream).
  - `GET /system/audit` — Immutable audit log trail.
  - `POST /system/backup` & `POST /system/restore` — Local hot DB backup/restore.
- **Devices & Pairing:**
  - `POST /devices/pairing/request` — Initiates pairing, returns 6-digit PIN.
  - `POST /devices/pairing/verify` — Validates PIN, issues 256-bit bearer token.
  - `GET /devices` & `GET /devices/{id}` — Enumerates paired devices.
  - `DELETE /devices/{id}/revoke` — Revokes authentication and kills active streams.
  - `GET /devices/pairing/pending` — Enumerates active unverified pairing codes.
- **Cameras & Streams:**
  - `GET /cameras` & `GET /cameras/{id}` — Camera listing and status.
  - `GET /streams` & `GET /streams/{camera_id}/preview` — Live MJPEG preview endpoint.
  - `GET /streams/{camera_id}/telemetry` — Frame count, FPS, and bitrate.
- **AI Runtimes:**
  - `GET /ai/status` — Active detector, backend, model loaded flag.
  - `GET /ai/models` & `GET /ai/metrics` — Performance and model metadata.
- **Events, Zones, Rules & Recordings:**
  - `GET /events` & `GET /events/{id}` — Query events and summaries.
  - `GET /zones` & `POST /zones` & `DELETE /zones/{id}` — Polygon zone CRUD.
  - `GET /rules` & `POST /rules` & `PUT /rules/{id}` & `DELETE /rules/{id}` — Event rules CRUD.
  - `GET /recordings` & `GET /recordings/{id}/file` — MP4 clip enumeration and playback.
- **WebSockets:**
  - `WS /api/v1/events/stream` — Real-time event broadcasting (`event_created`, `event_updated`, `event_resolved`).
  - `WS /api/v1/control/ws` — Camera telemetry and control commands.

---

## 4. Current Client UI Architecture

Located in `apps/client/`:
- Structure: Modular ES6 modules without external build tools or CDNs:
  - `index.html`: Shell layout, sidebar navigation, modal containers.
  - `css/styles.css`: Dark-themed palette (`#0f172a`, `#1e293b`, `#38bdf8`, `#22c55e`, `#ef4444`).
  - `js/app.js`: View router switching between views (`dashboard`, `cameras`, `live_view`, `events`, `event_detail`, `recordings`, `zones`, `rules`, `devices`, `ai_status`, `settings`).
  - `js/api.js`: Fetch wrapper for backend endpoints.
  - `js/ws.js`: WebSocket client connecting to `/api/v1/events/stream`.
  - `js/components/*.js`: View rendering components.

---

## 5. Current Event Model & Database Schema

- **Database Engine:** SQLite 3 in WAL mode (`smart_spectator.db`), schema version 3.
- **Core Tables:**
  - `devices`: `device_id`, `device_name`, `device_type`, `auth_token_hash`, `status`, `battery_level`, `last_seen`.
  - `cameras`: `camera_id`, `device_id`, `name`, `source_type`, `width`, `height`, `target_fps`, `status`.
  - `streams`: `stream_id`, `camera_id`, `current_fps`, `current_bitrate_kbps`, `dropped_frames_total`.
  - `zones`: `zone_id`, `camera_id`, `name`, `polygon_json`, `color`, `is_active`.
  - `event_rules`: `rule_id`, `name`, `is_active`, `condition_json`, `actions_json`, `severity_override`, `cooldown_seconds`.
  - `events`: `event_id`, `camera_id`, `task_id`, `recording_id`, `event_type`, `status`, `severity`, `confidence`, `summary`, `timestamp`, `start_time`, `end_time`, `involved_track_ids`, `zone_id`, `rule_id`, `explanation`, `metadata_json`.
  - `recordings`: `recording_id`, `camera_id`, `file_path`, `thumbnail_path`, `start_time`, `end_time`, `duration_seconds`, `file_size_bytes`, `codec`.
  - `audit_logs`: `log_id`, `timestamp`, `actor`, `action`, `resource`, `metadata_json`.
  - `schema_migrations`: `version`, `name`, `applied_at`.

---

## 6. Current Model Versions & Artifacts

- **YOLOv8n Detector:** Version `8.0.0`, ONNX FP32 (`detector_v1.onnx`), SHA-256: `05c0c73bb9bb9080447b1e986da7f40fbbed530280f472d0e3894263cc0565bd`.
- **SpectatorNet FP32:** Version `1.0.0`, ONNX FP32 (`spectatornet_v1.onnx`), SHA-256: `846724fd28fa2b344a88e90557177a22c51951634190d55855f666bb20b9ffc6`.
- **SpectatorNet INT8:** Version `1.0.0`, ONNX INT8 (`spectatornet_v1_int8.onnx`), SHA-256: `475585930c14a02b4b3374d37f9312a317c75dc7d1f6d6e29b9dbf2aeacc62a3`.

---

## 7. Current Limitations & Technical Debt

1. **Client UX & Visual Polish:**
   - Event search lacks advanced multi-field query parameters (e.g. date range, confidence range, duration, zone).
   - Recordings view lacks filtering by duration, date, or size, and lacks direct delete action with physical cleanup.
   - Camera management is fragmented across `cameras.js` and `devices.js`, without rich detail telemetry or connection history.
   - No interactive event timeline breakdown (e.g. object detected -> track established -> event confirmed -> clip saved).
2. **Notification & Prioritization Deficits:**
   - No local push notification framework with configurable audio/toast alerts and cooldown tiers.
   - Event priorities are currently static severities without deterministic priority scoring based on zone sensitivity, behavior, and duration.
3. **Zone & Rule Editing Workflow:**
   - Zone editor relies on basic canvas without vertex dragging handles, point insertion/deletion, or polygon self-intersection validation.
   - Rule builder lacks structured time-of-day condition schedules (e.g. `22:00-06:00`), class filtering, and multi-action triggers.
4. **Configuration & Operational Management:**
   - Configuration is hardcoded in environment variables and Pydantic defaults; no categorized configuration API (`SYSTEM`, `NETWORK`, `CAMERAS`, `AI`, `EVENTS`, `RECORDING`, `STORAGE`, `NOTIFICATIONS`, `SECURITY`) with secret-scrubbed export/import.
   - No automated event retention cleanup job for event records and orphan recordings.
5. **AI Model Registry & Lifecycle:**
   - Models are tightly bound to hardcoded paths; no extensible Model Registry abstraction allowing side-by-side A/B validation, runtime profiling, or manual activation.
6. **Deprecation Warnings:**
   - Widespread `datetime.utcnow()` deprecation warnings in test fixtures and model definitions.

---

## 8. Phase 9 Engineering Plan

Based on this audit, Phase 9 will implement:
- **Section 2 & 3:** Comprehensive UI/UX redesign and operational dashboard with live real-time event feed.
- **Section 4 & 5:** Unified camera management and deep camera detail page with real-time telemetry.
- **Section 6 & 7:** Intelligent event detail with natural language explanation generator and causal timeline milestones.
- **Section 8 & 9:** Event and recording multi-criteria search, sorting, pagination, and secure file deletion.
- **Section 10 & 11:** Local notification dispatcher with WebSocket notification events and configurable multi-tier cooldowns.
- **Section 12:** Deterministic smart event prioritization engine (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Section 13 & 14:** Interactive visual zone polygon editor and structured automation rule builder with time windows.
- **Section 15, 16 & 17:** AI diagnostics dashboard, local model registry, and model A/B comparison framework.
- **Section 18, 19 & 24:** Categorized configuration management, validation, safe export/import without secret leakage.
- **Section 20 & 21:** Storage dashboard and automated background retention cleanup job.
- **Section 22 & 23:** Operator activity logging and backup management UX.
- **Section 25 & 26:** API standardization and WebSocket protocol improvements with versioned schemas.
- **Section 28:** Hardened event engine test cases (midnight rules, cooldowns, camera disconnects).
- **Section 34:** Comprehensive Phase 9 test suite.
