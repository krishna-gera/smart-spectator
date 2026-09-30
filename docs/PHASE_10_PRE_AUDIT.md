# Phase 10 Pre-Audit: Advanced Intelligence & Architecture Readiness

**Document ID:** SS-DOC-033  
**Date:** 2026-09-30  
**Current Release:** v1.2.0 (Phase 9 Complete, 127/127 Passing Tests)  
**Target Release:** v2.0.0 (Phase 10 — Advanced Intelligence + Future Architecture)  
**Architecture Principles:** Local-First, Privacy-First, Offline-First, Model-Modular, Provider-Agnostic, Failure-Resilient.

---

## 1. Existing System Architecture Assessment

### 1.1 Primary AI Perception Pipeline
- **Ingestion**: Multi-camera TCP media streams (Port 8554, binary frame header `0x53530001` + H.264 NAL units).
- **Decoder**: PyAV / FFmpeg video worker decoding Annex B bitstreams into BGR NumPy arrays in bounded circular queues (`queue.Queue(maxsize=16)`).
- **Adaptive Frame Sampler**: Motion-gated dynamic sampling (1–15 FPS) based on frame pixel delta thresholds.
- **Spatial Object Detection (Level 1)**: YOLOv8n ONNX (`[1, 3, 640, 640]` $\to$ `[1, 84, 8400]`), extracting bounding boxes, classes (`person`, `vehicle`, etc.), and confidence scores.
- **Spatiotemporal Tracking (Level 2)**: ByteTrack with Kalman filtering and Hungarian IoU association, maintaining track histories in per-camera isolated contexts (`CameraAIContext`).
- **Feature Encoder**: Encodes 30-frame track trajectories into 166-dimensional kinematic vectors (normalized coordinates, velocities, accelerations, aspect ratios, bounding box dynamics).
- **Temporal Sequence Classifier (Level 3)**: SpectatorNet BiGRU (`[1, 30, 166]` $\to$ `[1, 6]`), producing action logits: `normal_transit`, `loitering`, `running`, `pacing`, `hesitation`, `boundary_approach`.

### 1.2 Event Architecture & Automation
- **Polygon ROI Evaluation**: Ray-casting point-in-polygon math validating whether track centroids or bottom-center points fall inside user-defined convex/concave zones.
- **Zone Types**: `detection`, `exclusion`, `loitering`, `transit`.
- **Compound Rules**: JSON-defined conditions matching event class, zone ID, dwell threshold duration, time-of-day windows, and priority overrides.
- **Event Engine**: Evaluates state transitions, applies temporal debouncing, checks thresholds, and outputs `EventRecord` with deterministic priority (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Causal Milestone Generator**: Generates chronological milestones with microsecond timestamps: `person_detected` $\to$ `zone_entered` $\to$ `temporal_pattern_detected` $\to$ `rule_condition_met` $\to$ `event_confirmed` $\to$ `recording_persisted`.
- **Notification Dispatcher**: 3-tier cooldown hierarchy (Global 5s, Camera 15s, Event Type 60s) with WebSocket streaming (Schema 1.2.0).

### 1.3 Database & Event History
- **Database Engine**: SQLite 3 with Write-Ahead Logging (`WAL`), foreign keys enabled, busy timeout 5000ms.
- **Schema Migrations**: 4 migrations applied (`devices`, `recordings`, `events`, `zones`, `rules`, `audit_logs`, `notification_configs`, `system_configs`).
- **Existing Event History**:
  - `events` table tracks `event_id`, `camera_id`, `event_type`, `priority`, `confidence`, `zone_id`, `track_id`, `start_time`, `end_time`, `details_json`, `timeline_milestones_json`, `recording_id`.
  - Filterable by `camera_id`, `event_type`, `priority`, `start_time`, `end_time`, `limit`, `offset`.
  - Retention cleaning prunes expired events while strictly preserving locked recordings (`is_locked = 1`).

### 1.4 Model Lifecycle & Verification
- **Model Registry (`ai/models/registry.py`)**: Catalogs local ONNX weights on disk (`detector_v1.onnx`, `spectatornet_v1.onnx`, `spectatornet_v1_int8.onnx`).
- **Cryptographic Verification**: Verifies SHA-256 against `manifest.json`.
- **Offline A/B Evaluator (`ai/models/ab_evaluator.py`)**: Runs side-by-side inference benchmarks measuring latency (mean, p50, p95), prediction agreement, and memory footprint.
- **Production Selection**: Explicit operator promotion; models with integrity mismatch cannot become active.

### 1.5 Provider & Hardware Abstraction
- **ProviderManager (`ai/inference/manager.py`)**: Tiered hardware provider fallback:
  1. `QNNExecutionProvider` (Qualcomm Hexagon NPU on Snapdragon X Elite/Plus)
  2. `DirectMLExecutionProvider` (Windows 11 GPU / NPU fallback)
  3. `CoreMLExecutionProvider` (macOS Apple Silicon host)
  4. `CPUExecutionProvider` (Universal standard baseline)

### 1.6 Camera Abstraction
- Currently tightly coupled to Android Camera Node via `StreamWorker` and TCP port 8554.
- Needs formal `CameraSource` interface to cleanly support future RTSP, ONVIF, and USB inputs without modifying downstream AI or recording layers.

---

## 2. Limitations of Current System
1. **Isolated Event Scope**: Events are instantaneous or duration-windowed triggers (`PERSON_ENTERED`, `LOITERING_DETECTED`), but the system does not link subsequent events into coherent relational sequences (e.g. `PERSON_ENTERED` $\to$ `OBJECT_REMOVED`).
2. **Lack of Macro Context**: The system lacks an environmental and stateful context engine (e.g., active event count, device state, time/day state, recent prior triggers) to synthesize broader incidents.
3. **Absence of Learned Baselines & Anomaly Scoring**: The system relies entirely on static thresholds without statistical rolling baselines (event frequency mean/stddev) to identify unusual activity.
4. **No Semantic Query Language**: Search is purely field-by-field REST query parameters; there is no structured semantic query representation or local query interpreter.
5. **No Structured Human Feedback / Active Learning Hooks**: Operators cannot submit structured verification feedback (`correct`, `incorrect`, `not_sure`) to track model accuracy or drift over time.

---

## 3. Performance Budget & Resource Isolation Strategy

To ensure advanced intelligence does not degrade the sub-100ms real-time vision pipeline:

| Execution Tier | Subsystems | Performance Target | Scheduling & Isolation |
|---|---|---|---|
| **Tier 1: REAL_TIME (Critical Path)** | TCP Ingestion, H.264 Decoder, YOLOv8n, ByteTrack, Feature Encoding, SpectatorNet, Zone/Rule Engine, MP4 Clip Packaging | $\le 15$ ms per sampled frame | Synchronous, dedicated threads, bounded queues, high priority |
| **Tier 2: EVENT_PROCESSING** | Deterministic Prioritization, Event Relationships, Incident Assembly, Multi-Tier Notifications | $\le 5$ ms per event | Event worker thread, asynchronous dispatch |
| **Tier 3: BACKGROUND_ANALYTICS** | Statistical Baseline Learning, Anomaly Calculation, Memory Summarization, Drift Tracking, Retention Pruning | Non-blocking (e.g., 100–500 ms) | Separate background worker/timer, low priority, yields under queue load |
| **Tier 4: ON-DEMAND QUERIES** | Semantic Search, Local Query Interpreter, Model Evaluation | Interactive ($\le 50$ ms) | REST request/response, bounded database reads |

---

## 4. Phase 10 Implementation Roadmap

1. **Semantic Event Model & Local Representation**: Observation $\to$ Prediction $\to$ Event $\to$ Context $\to$ Incident hierarchy with normalized entity-action schemas.
2. **Event Relationship Engine**: Temporal event chaining (`followed_by`, `co_occurs_with`, `correlated_with`, `camera_handoff`).
3. **Context Engine & Incident Engine**: Stateful environmental context and rule-driven incident generation (`AFTER_HOURS_ENTRY`, `PERIMETER_BREACH_UNRESOLVED`).
4. **Local Event Memory & Statistical Baselines**: SQLite-backed event memory, rolling mean/stddev activity baselines, and statistical z-score anomaly detection (`UNUSUAL_ACTIVITY_FREQUENCY`).
5. **Local Query Engine & Command Interpreter**: Structured query objects and deterministic natural language command parser.
6. **Local AI Model Orchestrator & Language Model Adapter**: Abstract provider interfaces (`LocalLanguageModelProvider`, `TaskClassifier`, `ActionSafetyValidator`) ensuring 0% uncontrolled autonomy.
7. **Camera Source Abstraction**: Pluggable `CameraSource` interface (`AndroidCameraSource`, `RTSPCameraSource` stub, `ONVIFCameraSource` stub, `USBCameraSource` stub).
8. **Model Evolution, Human Feedback & Drift Monitoring**: Dataset versioning metadata, evaluation scripts (`scripts/evaluate_model.py`), human feedback store, and confidence drift tracking.
9. **REST APIs & Security**: `/api/v1/query`, `/api/v1/incidents`, `/api/v1/anomalies`, `/api/v1/memory`, `/api/v1/feedback` with strict validation against SQL/path injection.
10. **Comprehensive Phase 10 Test Suite**: 12 test modules covering all new engines and abstractions.
