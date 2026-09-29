# Smart Spectator — Final System Architecture Specification

**Document ID:** SS-DOC-032  
**Version:** 1.2.0  
**Phase:** 9 (Polished Intelligent Local Monitoring Product)  
**Date:** 2026-09-30  
**Status:** Certified Architecture Specification  

---

## 1. System Vision & Architecture Topology

Smart Spectator is an enterprise-grade, 100% local-first visual intelligence platform engineered for edge computing devices (Qualcomm Snapdragon X Elite/Plus, Apple Silicon, and x86_64 PC/Linux). It transforms consumer Android mobile phones into intelligent smart cameras, performing real-time spatial object detection, persistent multi-object tracking, temporal behavioral reasoning, and spatial rule enforcement without any cloud or internet dependencies.

### Complete ASCII System Architecture Diagram

```
+===================================================================================================================+
|                                           SMART SPECTATOR SYSTEM TOPOLOGY                                         |
+===================================================================================================================+
|                                                                                                                   |
|   +-------------------------------------------------------------+                                                 |
|   |                 COMMODITY ANDROID CAMERA NODE               |                                                 |
|   |  - CameraX / Camera2 720p/1080p @ 30 FPS                   |                                                 |
|   |  - Hardware H.264 Encoder (MediaCodec / Qualcomm Adreno)    |                                                 |
|   |  - Binary Protocol Packetizer (Magic: 0x53530001 + CRC32)   |                                                 |
|   |  - Zero-Config Hub Discovery (mDNS: _smart-spectator._tcp)  |                                                 |
|   +-------------------------------------------------------------+                                                 |
|                                  |                                                                                |
|                                  | [ Private Wi-Fi LAN / 802.11ac/ax ]                                            |
|                                  |   * Egress TCP to Port 8554 (Binary Video Stream)                              |
|                                  |   * Egress HTTP/WS to Port 8000 (REST Auth & Control)                          |
|                                  v                                                                                |
|   +===========================================================================================================+   |
|   |                        SNAPDRAGON DESKTOP HUB (WINDOWS 11 ARM64 / COPILOT+ PC)                           |   |
|   |                                                                                                           |   |
|   |   +---------------------------------------------------------------------------------------------------+   |   |
|   |   |                                      NETWORK & INGESTION LAYER                                    |   |   |
|   |   |  - TCP Media Receiver (Port 8554): Non-blocking socket reader, gap detection, CRC32 validation   |   |   |
|   |   |  - H.264 Video Decoder (PyAV / FFmpeg): Annex B NAL demuxing to raw BGR NumPy frames             |   |   |
|   |   |  - mDNS Hub Advertiser (Port 5353 multicast): Zero-configuration discovery beacon                |   |   |
|   |   |  - FastAPI Gateway (Port 8000): REST endpoints, WebSocket control & event broadcasting            |   |   |
|   |   +---------------------------------------------------------------------------------------------------+   |   |
|   |                                  |                                       |                                |   |
|   |                                  v                                       v                                |   |
|   |   +---------------------------------------------------+   +-------------------------------------------+   |   |
|   |   |            AI PERCEPTION PIPELINE                 |   |           STORAGE & RECORDING             |   |   |
|   |   |                                                   |   |                                           |   |   |
|   |   |  [ Adaptive Frame Sampler & Motion Gate ]         |   |  [ Circular In-Memory Frame Ring Buffer ] |   |   |
|   |   |   - Decimates 30 FPS to 5-10 FPS target           |   |   - Retains 5s pre-roll history (150 frm) |   |   |
|   |   |   - Skips inference on static backgrounds         |   |                                           |   |   |
|   |   |                     |                             |   |  [ MP4 Clip Synthesizer ]                 |   |   |
|   |   |                     v                             |   |   - H.264 container muxer                 |   |   |
|   |   |  [ Level 1: YOLOv8n Spatial Detector ]            |   |   - Encodes: pre-roll + active + post     |   |   |
|   |   |   - ONNX Runtime via Qualcomm Hexagon NPU (QNN)   |   |   - Path: recordings/event_<id>.mp4       |   |   |
|   |   |   - DirectML / CoreML / CPU fallback chain        |   |                                           |   |   |
|   |   |   - Latency: 3.38ms (Host CoreML)                 |   |  [ Storage Lifecycle Manager ]            |   |   |
|   |   |                     |                             |   |   - 20 GB quota / 7-day retention         |   |   |
|   |   |                     v                             |   |   - Degraded mode if disk < 500 MB        |   |   |
|   |   |  [ Level 2: ByteTrack Multi-Object Tracker ]      |   |   - FIFO eviction of oldest video clips   |   |   |
|   |   |   - Isolated tracker state per camera node        |   +-------------------------------------------+   |   |
|   |   |   - Kalman Filter + Hungarian IoU matching        |                          ^                        |   |
|   |   |   - Persistent trajectory IDs across occlusions   |                          |                        |   |
|   |   |                     |                             |                          | (Trigger Recording)    |   |
|   |   |                     v                             |                          |                        |   |
|   |   |  [ Structured Observation Assembly ]              |                          |                        |   |
|   |   +---------------------------------------------------+                          |                        |   |
|   |                         |                                                        |                        |   |
|   |                         v                                                        |                        |   |
|   |   +------------------------------------------------------------------------------+--------------------+   |   |
|   |   |                               TEMPORAL INTELLIGENCE & EVENT ENGINE                                |   |   |
|   |   |                                                                                                   |   |   |
|   |   |  [ Level 3: SpectatorNet Recurrent Neural Network (GRU) ]                                         |   |   |
|   |   |   - 16-frame sliding observation window (3.2s history) encoded into 64-dim feature vectors       |   |   |
|   |   |   - INT8 quantized ONNX running in 0.25ms on Hexagon NPU / CoreML                                 |   |   |
|   |   |   - Classifies: NORMAL, PERSON_ENTERED, LOITERING, OBJECT_LEFT, RAPID_MOTION, CAMERA_BLOCKED      |   |   |
|   |   |                                                                                                   |   |   |
|   |   |  [ Event Engine & Spatial Rule Evaluator ]                                                        |   |   |
|   |   |   - Ray-casting point-in-polygon containment test for user-defined zones                          |   |   |
|   |   |   - State machine: DETECTED -> ACTIVE -> RESOLVED                                                 |   |   |
|   |   |   - Emits structured Event schemas to persistence and WebSocket push                              |   |   |
|   |   +---------------------------------------------------------------------------------------------------+   |   |
|   |                         |                                                        |                        |   |
|   |                         v                                                        v                        |   |
|   |   +-------------------------------------------+   +---------------------------------------------------+   |   |
|   |   |          LOCAL METADATA DATABASE          |   |              DIAGNOSTICS & TELEMETRY              |   |   |
|   |   |                                           |   |                                                   |   |   |
|   |   |  - SQLite 3 with Write-Ahead Logging (WAL)|   |  - Unified Diagnostics: 11 Subsystem Inspection   |   |   |
|   |   |  - Tables: devices, cameras, events,      |   |  - Model Validator: SHA-256 Manifest Checksums    |   |   |
|   |   |    zones, event_rules, audit_logs         |   |  - Hardware Info: Silicon & Accelerators          |   |   |
|   |   |  - Hot online backup & safe restore       |   |  - Audit Trail: Immutable append-only log         |   |   |
|   |   +-------------------------------------------+   +---------------------------------------------------+   |   |
|   +===========================================================================================================+   |
|                                                      |                                                            |
|                                                      v [ Local HTTP / WebSocket (Port 8000) ]                     |
|   +-----------------------------------------------------------------------------------------------------------+   |
|   |                                        MONITORING CLIENT / WEB UI                                         |   |
|   |  - Live H.264 / MJPEG Stream Canvas Preview with Bounding Box Overlays & Track Trajectories               |   |
|   |  - Interactive Polygonal Spatial Zone Creation & Editing                                                  |   |
|   |  - Real-Time WebSocket Event Feed with Instant Alert Badges & MP4 Video Playback Modals                  |   |
|   |  - Comprehensive Subsystem Health & Hardware Acceleration Telemetry Gauges                                |   |
|   +-----------------------------------------------------------------------------------------------------------+   |
+===================================================================================================================+
```

---

## 2. Subsystem Interaction Matrix

| Source Subsystem | Target Subsystem | Interaction Type | Transport / Mechanism | Primary Data Transferred |
| :--- | :--- | :--- | :--- | :--- |
| **Android Camera** | **Device Manager** | Pairing / Discovery | mDNS (`5353`) + REST (`8000`) | 6-Digit PIN, Device Info, Bearer Token |
| **Android Camera** | **Stream Engine** | Ingestion | Persistent TCP (`8554`) | H.264 NAL units in `0x53530001` packets |
| **Stream Engine** | **Recorder** | Frame Buffer | In-memory circular buffer | Decoded raw BGR video frames |
| **Stream Engine** | **AI Pipeline** | Ingestion Sampling | Non-blocking bounded queue | Decimated 5–10 FPS video frames |
| **AI Pipeline (L1/L2)** | **Observation Builder**| Perception | Function invocation | Normalized bounding boxes & tracklets |
| **Observation Builder**| **SpectatorNet (L3)** | Feature Extraction | Sliding tensor `(1,16,64)` | Spatiotemporal feature representations |
| **SpectatorNet (L3)** | **Event Engine** | Behavioral Classification| In-memory event callback | Categorical behavioral probabilities |
| **Event Engine** | **Recorder** | Event Trigger | Asynchronous queue | Clip generation start/stop commands |
| **Event Engine** | **Database** | Persistence | SQLite connection (WAL) | Event records, severity, timestamps |
| **Event Engine** | **WebSocket Hub** | Alert Broadcast | WebSocket push (`/events/ws`) | Real-time JSON event notifications |
| **Web UI** | **FastAPI Hub** | Management & Playback | HTTP REST (`/api/v1/*`) | Zone polygons, rule config, MP4 clips |

---

## 3. Network Topology & Port Mapping

| Port | Protocol | Interface | Direction | Service / Function |
| :--- | :--- | :--- | :--- | :--- |
| **5353** | UDP | Multicast (`224.0.0.251`) | Bidirectional | Zero-configuration mDNS Hub service broadcast (`_smart-spectator._tcp`) |
| **8000** | TCP | `0.0.0.0` (LAN) | Inbound | FastAPI REST Gateway, WebSocket event/control streams, Client UI static files |
| **8554** | TCP | `0.0.0.0` (LAN) | Inbound | Dedicated binary media receiver for phone H.264 video streams |

> [!IMPORTANT]
> All network listeners bind strictly to private local area networks (LANs). Zero ports are exposed to WAN, and zero outbound network calls are initiated to external cloud servers.

---

## 4. Codebase Directory Structure

```
smart-spectator/
├── RELEASE_MANIFEST.json           # Cryptographic release manifest (v1.1.0)
├── requirements.txt                # Pinned production Python dependencies
├── pytest.ini                      # Test runner configuration
├── README.md                       # Product overview, quickstart & runbook
│
├── ai/                             # Artificial Intelligence Core
│   ├── inference/                  # Execution provider manager & runtime
│   │   ├── manager.py              # Dynamic provider selection (QNN/DML/CoreML/CPU)
│   │   └── providers/              # Hardware-specific execution adapters
│   ├── models/                     # ONNX neural network weights
│   │   ├── releases/               # Production release models & manifest
│   │   │   ├── manifest.json       # SHA-256 release checksums
│   │   │   ├── detector_v1.onnx    # YOLOv8n Level 1 spatial detector (FP32)
│   │   │   ├── spectatornet_v1.onnx # SpectatorNet Level 3 temporal GRU (FP32)
│   │   │   └── spectatornet_v1_int8.onnx # SpectatorNet Level 3 (INT8 Quantized)
│   │   └── validator.py            # SHA-256 checksum integrity verification
│   └── spectatornet/               # SpectatorNet model definition & feature encoder
│       ├── model.py                # PyTorch / ONNX recurrent architecture
│       ├── features.py             # 64-dimensional temporal feature extractor
│       └── quantize.py             # Post-training INT8 quantization script
│
├── apps/camera/                    # Android Flutter Camera Application
│   ├── pubspec.yaml                # Flutter project specification (v1.1.0+2)
│   ├── lib/                        # Flutter Dart UI & streaming services
│   └── android/app/                # Android platform native code
│       ├── build.gradle.kts        # Android build configuration
│       └── src/main/
│           ├── AndroidManifest.xml # Audited local permissions (Camera, Wi-Fi LAN)
│           └── kotlin/.../         # CameraX capture & MediaCodec H.264 pipeline
│
├── docs/                           # Architecture, Runbooks & Audit Documentation
│   ├── 18_PPT_ARCHITECTURE_NOTES.md # Slide-by-slide challenge deck talking points
│   ├── ANDROID_RELEASE.md          # Android build, APK install & lifecycle guide
│   ├── DEMO_RUNBOOK.md             # 5 deterministic live demonstration scenarios
│   ├── FINAL_AI_ARCHITECTURE.md    # 3-level perception & inference deep dive
│   ├── FINAL_DATA_FLOW.md          # 16-stage end-to-end data flow specification
│   ├── FINAL_PROJECT_REPORT.md     # Comprehensive 9-phase final project report
│   ├── FINAL_SECURITY_AUDIT.md     # Production security and airgap verification
│   ├── FINAL_SYSTEM_ARCHITECTURE.md# System topology, diagrams & port allocations
│   ├── PHASE_8_PRE_AUDIT.md        # Pre-audit validation report
│   ├── PHASE_8_SECURITY_AUDIT.md   # Air-gap verification & static audit
│   ├── PHASE_8_VALIDATION_MATRIX.md# Comprehensive 11-subsystem test matrix
│   ├── REAL_HARDWARE_VALIDATION.md # Host CoreML & Snapdragon NPU benchmarks
│   ├── REAL_WORLD_EVENT_VALIDATION.md # Real-world false positive reduction tests
│   ├── SNAPDRAGON_DEMO_STORY.md    # Qualcomm Build & Present presentation story
│   └── WINDOWS_INSTALLATION.md     # Windows on Snapdragon deployment runbook
│
├── scripts/                        # Production Operations & Deployment Scripts
│   ├── doctor.py                   # Pre-flight environment & subsystem validator
│   ├── health_windows.ps1          # Windows health probe PowerShell script
│   ├── install_windows.ps1         # Windows on Snapdragon automated installer
│   ├── live_pipeline_diagnostics.py# Live end-to-end frame verification script
│   ├── run_demo.py                 # 9-step deterministic demo verification harness
│   ├── service_status.ps1          # Windows background service query script
│   ├── start_windows.ps1           # Windows startup launcher with log redirection
│   ├── stop_windows.ps1            # Windows graceful process terminator
│   ├── uninstall_windows.ps1       # Clean uninstaller for Windows
│   └── validate_snapdragon_runtime.py # Benchmark suite for ONNX providers
│
├── services/                       # Hub Core Services
│   ├── ai_engine/                  # Perception Pipeline (Detection & Tracking)
│   │   ├── detector.py             # YOLOv8n ONNX inference & letterbox preprocessing
│   │   ├── tracker.py              # ByteTrack association & Kalman filter state
│   │   ├── frame_sampler.py        # Motion-gated adaptive frame decimation
│   │   ├── observation_builder.py  # Structured Observation schema generator
│   │   └── pipeline.py             # Multi-camera async pipeline orchestrator
│   ├── device_manager/             # Node Pairing, Discovery & Authentication
│   │   ├── discovery.py            # Zeroconf mDNS advertisement
│   │   └── manager.py              # 6-digit PIN validation & token issuance
│   ├── event_engine/               # Rules, Spatial Zones & Video Recording
│   │   ├── engine.py               # Asynchronous event state machine
│   │   ├── rules.py                # Temporal & behavioral rule evaluator
│   │   ├── zones.py                # Polygonal spatial boundary evaluator
│   │   └── recording.py            # Circular buffer pre-roll & MP4 clip generator
│   ├── hub_backend/                # FastAPI Application & Storage
│   │   ├── client/                 # Monitoring Client SPA static assets
│   │   ├── database/               # SQLite WAL connection, migrations & backup
│   │   ├── routes/                 # REST endpoints (health, system, events, etc.)
│   │   ├── security/               # Log sanitization & token authentication
│   │   ├── websocket/              # Event push & control WebSocket handlers
│   │   ├── config.py               # Central environment settings (v1.1.0)
│   │   └── main.py                 # FastAPI application factory & lifespan
│   └── stream_engine/              # TCP Ingestion & Video Parsing
│       ├── protocol.py             # Wire format packet pack/unpack & CRC32
│       └── server.py               # Non-blocking TCP server & PyAV H.264 decoder
│
├── shared/                         # Common Protocols & Standard Schemas
│   ├── protocols/                  # Python typing protocols for AI and cameras
│   └── schemas/v1/                 # Pydantic data models for events, devices, etc.
│
└── tests/                          # Automated Pytest Test Suite (100 Passing Tests)
    ├── test_ai_pipeline.py
    ├── test_hub_api.py
    ├── test_multi_camera_isolation.py
    ├── test_offline_mode.py
    ├── test_pairing_auth.py
    ├── test_phase3_spectatornet.py
    ├── test_phase4_apis.py
    ├── test_phase4_end_to_end.py
    ├── test_phase4_event_engine.py
    ├── test_phase4_recording.py
    ├── test_phase4_rules.py
    ├── test_phase4_zones.py
    ├── test_phase6_database_backup.py
    ├── test_phase6_health_and_lifecycle.py
    ├── test_phase6_security.py
    ├── test_phase6_storage_lifecycle.py
    ├── test_phase7_snapdragon_inference.py
    ├── test_phase8_database_recovery.py
    ├── test_phase8_diagnostics_and_fallback.py
    ├── test_phase8_model_integrity.py
    ├── test_protocol.py
    └── test_stream_ingest.py
```

---

## 5. Snapdragon Acceleration Points

1. **Dedicated Hexagon NPU Offloading:**
   - Level 1 spatial object detection evaluated via `QNNExecutionProvider` on Hexagon NPU tensor cores.
   - Level 3 SpectatorNet temporal GRU evaluated in INT8 precision, taking advantage of Hexagon vector extensions (HVX).
2. **Qualcomm DirectML GPU Acceleration:**
   - On Windows 11 ARM64 configurations where QNN is pending runtime components, the pipeline automatically falls back to `DmlExecutionProvider`, utilizing the Adreno GPU without user intervention.
3. **Oryon CPU Core Offload:**
   - Decoupled worker threads handle TCP stream ingestion and video frame decoding, keeping memory bus overhead isolated from inference execution.

---

## 6. Air-Gap & Privacy Guarantees

- **Zero Cloud Network Calls:** The entire codebase contains no external HTTP requests, no third-party cloud analytics, and no remote license validators.
- **Local Network Encapsulation:** Camera streams and event metadata never leave the local Wi-Fi subnet.
- **Tamper Resistance:** Model weights are authenticated against SHA-256 hashes at launch.
- **Fail-Safe Operation:** In the event of a total WAN outage or severed internet uplink, Smart Spectator continues detecting, recording, and alerting locally with zero disruption.
