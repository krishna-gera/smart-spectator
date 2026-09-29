# Smart Spectator 👁️⚡

> **A Local-First Visual Intelligence Ecosystem for Snapdragon-Powered PCs and Repurposed Edge Nodes.**  
> Developed for the **Snapdragon AI Lab Build & Present Challenge**.

---

## 🌟 Project Vision

Smart Spectator turns everyday Android smartphones into high-definition, intelligent camera nodes orchestrated by a central **Snapdragon-powered Desktop Hub**.

By offloading compute to the **45+ TOPS Qualcomm Hexagon NPU** on Snapdragon X-Series platforms, Smart Spectator delivers real-time spatial object detection, multi-object temporal tracking, and custom event reasoning (**SpectatorNet**) completely within the local network—with **zero cloud dependency, zero subscription costs, and guaranteed privacy**.

```
Android Camera Node (Flutter / Kotlin)
       ↓ (Low-latency H.264 over local Wi-Fi)
Smart Spectator Desktop Hub (FastAPI + SQLite WAL)
       ↓ (Snapdragon Hexagon NPU / Qualcomm QNN)
Multi-Stage AI Perception (Detection → Tracking → SpectatorNet)
       ↓
Event & Decision Engine (ROI Zones / Dwell Logic)
       ↓
Local Storage (SQLite WAL + Rolling Ring Buffer MP4)
       ↓
Monitoring Client Dashboard & Real-Time Alerts
```

---

### 🚀 Phase Status

- **Phase 0 (Architecture & Foundation):** ✅ **COMPLETED** (18 Master Specifications, Shared Protocols, Contracts)
- **Phase 1 (Core Streaming & Pairing):** ✅ **COMPLETED** (FastAPI Core, SQLite WAL, mDNS Discovery, 6-Digit PIN Pairing, Binary Framing Protocol, Live Preview, Android Camera App)
- **Phase 2 (AI Perception & Hardware Acceleration):** ✅ **COMPLETED** (YOLOv8n ONNX, ByteTrack Multi-Object Tracking, Adaptive Frame Sampler, Motion Gating, Bounded Queue AI Pipeline, InferenceProvider Hierarchy, Observation Contract)
- **Phase 3 (Custom Dataset & SpectatorNet Training):** ✅ **COMPLETED** (Observation sequence dataset pipeline, Feature Encoder, Session split with zero leakage, Dataset Validator, SpectatorNet BiGRU Attention Model, ONNX numerical export & validation, INT8 Quantization, Predictor Phase 4 contract)
- **Phase 4 (Event Engine, Automation & Recording):** ✅ **COMPLETED** (Event Engine, Confidence Filtering, Temporal Debouncing, State Machine, Ray-Casting Polygon Zones, JSON Rule Builder, Circular Rolling Buffer, Pre/Post-Roll MP4 Clip Encoding)
- **Phase 5 (Monitoring Client Application):** ✅ **COMPLETED** (Operator-grade single page app, OLED dark theme, Multi-camera grid, Live view with bounding box overlays, Interactive polygon canvas, Rule manager, Event inspector, MP4 clip player, System telemetry)
- **Phase 6 (Production Hardening & Device Integration):** ✅ **COMPLETED** (Centralized configuration, rotating logs with secret sanitization, shallow/deep health checks `/health/detailed`, SQLite versioned migrations, online hot backup/restore, 500MB disk guard, Android lifecycle handling and exponential backoff)
- **Phase 7 (Snapdragon Optimization & Final Validation):** ✅ **COMPLETED** (Tiered inference fallback QNN -> DirectML/CoreML -> CPU, versioned model releases FP32/INT8 in `ai/models/releases/`, real hardware benchmarking suite, CI/CD pipeline, demo scenario runner, release packaging v1.0.0)

---

## 📂 Repository Structure

```
smart-spectator/
│
├── apps/
│   ├── camera/           # Android Camera Node (Flutter + CameraX + Lifecycle)
│   └── client/           # Responsive Monitoring Client (Web / Mobile)
│
├── services/
│   ├── hub_backend/      # FastAPI local orchestrator, REST, WebSockets & Storage
│   │   ├── database/     # Migrations, connection pool, online backup & restore
│   │   └── routes/       # Health, System, Devices, Streams, Events, Rules, Zones
│   ├── stream_engine/    # Hardware video ingestion, demuxer & circular ring buffers
│   ├── ai_engine/        # Multi-stage perception orchestrator & inference runtimes
│   └── event_engine/     # State machines, ROI evaluation, policy triggers & clip recorder
│
├── ai/
│   ├── models/releases/  # Versioned release ONNX/INT8 models & manifest.json
│   ├── training/         # PyTorch pipelines for custom SpectatorNet model
│   ├── datasets/         # Manifests, annotations & tools for Smart Spectator Dataset
│   └── inference/        # Hardware providers (Hexagon NPU, DirectML, CoreML, CPU)
│
├── shared/
│   ├── schemas/v1/       # Versioned Pydantic data contracts (Device, Camera, Event, etc.)
│   ├── protocols/        # Hardware abstractions (CameraSource, InferenceProvider, AIModel)
│   └── constants/        # System ports, timeouts, default buffer configurations
│
├── docs/                 # Complete Architecture & Implementation Specifications
│   ├── PHASE_6_IMPLEMENTATION.md  # Production Hardening details
│   ├── PHASE_7_IMPLEMENTATION.md  # Snapdragon Optimization & Benchmark details
│   ├── HARDWARE_BENCHMARKS.md     # Measured edge latency & throughput distributions
│   ├── DEPLOYMENT_GUIDE.md        # Production edge installation & systemd setup
│   └── ...
│
├── scripts/
│   ├── start_dev.sh          # Single-command development launcher
│   ├── start_production.sh   # Production background launcher
│   ├── benchmark_hardware.py # Real hardware profiling harness
│   └── demo_scenarios.py     # Deterministic multi-scenario event demo runner
│
├── tests/                # 85 automated unit, integration, and E2E tests (Pytest)
└── README.md
```

---

## 🛠️ Quickstart Guide

### 1. Launch Desktop Hub
Development Mode:
```bash
./scripts/start_dev.sh
```
Production Mode:
```bash
./scripts/start_production.sh
```
- Open **`http://localhost:8000/client`** for the **Operator Monitoring Client (SPA)**.
- Open **`http://localhost:8000/health/detailed`** for the **Sub-System Health Diagnostics**.
- Open **`http://localhost:8000/docs`** for interactive Swagger REST API documentation.

### 2. Run Automated Verification Tests
```bash
# Run all 85 unit, integration, and end-to-end tests
PYTHONPATH=. pytest -v
```

### 3. Run Hardware Benchmarking Harness
```bash
python3 scripts/benchmark_hardware.py
```

### 4. Run End-to-End Demo Scenarios
```bash
python3 scripts/demo_scenarios.py
```

### 5. Run Android Camera Node
```bash
cd apps/camera
flutter run
```
- The app automatically discovers the Hub on the local Wi-Fi via mDNS (`_smartspectator._tcp.local.`).
- Input the 6-digit verification code shown on the Desktop Hub dashboard.
- Tap **"Start Streaming"** to begin transmitting 720p @ 30 FPS video to the Hub.
