# Smart Spectator 👁️⚡

> **A Local-First Visual Intelligence Ecosystem for Snapdragon-Powered PCs and Repurposed Edge Nodes.**  
> Developed for the **Qualcomm Snapdragon AI Lab Build & Present Challenge**.  
> **Release Version:** `1.1.0` | **Status:** Production Hardened & Challenge Ready | **Tests:** 100/100 PASSING

---

## 🌟 Project Vision

Smart Spectator transforms ordinary Android smartphones into high-definition, intelligent camera nodes orchestrated by a central **Snapdragon-powered Desktop Hub (Copilot+ PC)**.

By offloading neural inference to the **45+ TOPS Qualcomm Hexagon NPU** on Snapdragon X-Series platforms, Smart Spectator delivers real-time spatial object detection, multi-object temporal tracking, and custom event reasoning (**SpectatorNet**) completely within the local network—with **zero cloud dependency, zero subscription costs, and guaranteed privacy**.

```
Android Camera Node (Flutter / Kotlin / MediaCodec H.264)
       ↓ (Low-latency TCP Stream over Local Wi-Fi / Port 8554)
Smart Spectator Desktop Hub (FastAPI + SQLite WAL / Port 8000)
       ↓ (Snapdragon Hexagon NPU / Qualcomm QNN / DirectML)
Multi-Stage AI Perception (YOLOv8n → ByteTrack → SpectatorNet GRU)
       ↓
Event & Decision Engine (ROI Polygon Zones / Temporal Rules)
       ↓
Local Storage (SQLite WAL + Circular Ring Buffer MP4 Recordings)
       ↓
Monitoring Client Web Dashboard & WebSocket Real-Time Alert Feed
```

---

## 🚀 Engineering Phase Status

- **Phase 0 (Architecture & Foundation):** ✅ **COMPLETED** (18 Master Specifications, Shared Protocols, Contracts)
- **Phase 1 (Core Streaming & Pairing):** ✅ **COMPLETED** (FastAPI Core, SQLite WAL, mDNS Discovery, 6-Digit PIN Pairing, Binary Framing Protocol, Live Preview, Android Camera App)
- **Phase 2 (AI Perception & Hardware Acceleration):** ✅ **COMPLETED** (YOLOv8n ONNX, ByteTrack Multi-Object Tracking, Adaptive Frame Sampler, Motion Gating, Bounded Queue AI Pipeline, InferenceProvider Hierarchy, Observation Contract)
- **Phase 3 (Custom Dataset & SpectatorNet Training):** ✅ **COMPLETED** (Observation sequence dataset pipeline, Feature Encoder, Session split with zero leakage, Dataset Validator, SpectatorNet BiGRU Attention Model, ONNX numerical export & validation, INT8 Quantization, Predictor Contract)
- **Phase 4 (Event Engine, Automation & Recording):** ✅ **COMPLETED** (Event Engine, Confidence Filtering, Temporal Debouncing, State Machine, Ray-Casting Polygon Zones, JSON Rule Builder, Circular Rolling Buffer, Pre/Post-Roll MP4 Clip Encoding)
- **Phase 5 (Monitoring Client Application):** ✅ **COMPLETED** (Operator-grade single page app, OLED dark theme, Multi-camera grid, Live view with bounding box overlays, Interactive polygon canvas, Rule manager, Event inspector, MP4 clip player, System telemetry)
- **Phase 6 (Production Hardening & Device Integration):** ✅ **COMPLETED** (Centralized configuration, rotating logs with secret sanitization, health diagnostics `/health/detailed`, SQLite versioned migrations, online hot backup/restore, 500MB disk guard, Android lifecycle handling and exponential backoff)
- **Phase 7 (Snapdragon Optimization & Model Releases):** ✅ **COMPLETED** (Tiered inference fallback QNN -> DirectML/CoreML -> CPU, versioned model releases FP32/INT8 in `ai/models/releases/`, real hardware benchmarking suite, CI/CD pipeline, demo scenario runner, release packaging v1.0.0)
- **Phase 8 (Real-Device Deployment, End-to-End Validation & Demo Readiness):** ✅ **COMPLETED** (Windows on Snapdragon deployment toolchain `install_windows.ps1`, Android production release auditing, unified 11-subsystem diagnostics endpoint `/api/v1/system/diagnostics`, model integrity SHA-256 validation, first-run doctor `scripts/doctor.py`, hardware runtime benchmark `scripts/validate_snapdragon_runtime.py`, deterministic demo runner `scripts/run_demo.py`, 100 automated unit & integration tests)

---

## ⚡ Real Hardware Performance Profile

Measured on host silicon using `scripts/validate_snapdragon_runtime.py` (100 warm iterations per model):

| Model Artifact | Precision | Execution Provider | P50 Latency | Throughput | Snapdragon Hexagon NPU (Expected) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SpectatorNet** | FP32 | `CoreMLExecutionProvider` | **0.21 ms** | **4,501 FPS** | `< 0.20 ms` | `MEASURED` |
| **SpectatorNet** | INT8 | `CoreMLExecutionProvider` | **0.25 ms** | **3,910 FPS** | `< 0.15 ms` | `MEASURED` |
| **YOLOv8n Detector** | FP32 | `CoreMLExecutionProvider` | **3.38 ms** | **286.9 FPS** | `1.8 – 2.5 ms` | `MEASURED` |

---

## 📂 Repository Structure

```
smart-spectator/
├── RELEASE_MANIFEST.json           # Cryptographic release manifest (v1.1.0)
├── requirements.txt                # Pinned production Python dependencies
│
├── apps/
│   ├── camera/                     # Android Camera Node (Flutter + CameraX + MediaCodec)
│   └── client/                     # Monitoring Client Web App (HTML5 / ES6 / Canvas)
│
├── services/
│   ├── hub_backend/                # FastAPI Hub, SQLite WAL, WebSockets & REST APIs
│   ├── stream_engine/              # TCP Media Ingestion (Port 8554), CRC32 & H.264 Decoder
│   ├── ai_engine/                  # Perception Pipeline (YOLOv8n + ByteTrack + Frame Sampler)
│   ├── event_engine/               # Temporal Rules, Polygon Zones & MP4 Clip Synthesizer
│   └── device_manager/             # Zeroconf mDNS Discovery & 6-Digit PIN Pairing
│
├── ai/
│   ├── models/releases/            # Production ONNX models & manifest.json
│   ├── inference/                  # Execution provider manager (QNN, DirectML, CoreML, CPU)
│   └── spectatornet/               # Custom temporal GRU architecture & INT8 quantization
│
├── docs/                           # Comprehensive Specifications & Operations Guides
│   ├── DEMO_RUNBOOK.md             # 5 deterministic live demonstration scenarios
│   ├── WINDOWS_INSTALLATION.md     # Windows on Snapdragon deployment runbook
│   ├── ANDROID_RELEASE.md          # Android APK release & lifecycle guide
│   ├── REAL_HARDWARE_VALIDATION.md # Silicon benchmarking & execution provider tests
│   ├── REAL_WORLD_EVENT_VALIDATION.md # Temporal false positive reduction validation
│   ├── SNAPDRAGON_DEMO_STORY.md    # Qualcomm challenge pitch & demonstration story
│   ├── 18_PPT_ARCHITECTURE_NOTES.md # 12-slide challenge presentation deck
│   ├── FINAL_SYSTEM_ARCHITECTURE.md# System topology, diagrams & port allocations
│   ├── FINAL_DATA_FLOW.md          # 16-stage end-to-end data flow specification
│   ├── FINAL_AI_ARCHITECTURE.md    # 3-level perception & inference deep dive
│   ├── FINAL_SECURITY_AUDIT.md     # Security audit & air-gap verification
│   └── FINAL_PROJECT_REPORT.md     # 9-phase final project report
│
├── scripts/                        # Production Automation & Diagnostics
│   ├── doctor.py                   # First-run diagnostic doctor
│   ├── validate_snapdragon_runtime.py # ONNX execution provider benchmark suite
│   ├── live_pipeline_diagnostics.py# Live end-to-end frame verification
│   ├── run_demo.py                 # 9-step deterministic demo workflow
│   ├── install_windows.ps1         # Windows on Snapdragon installer
│   ├── start_windows.ps1           # Windows startup launcher
│   ├── stop_windows.ps1            # Windows service terminator
│   ├── health_windows.ps1          # Windows health probe
│   └── service_status.ps1          # Windows process monitor
│
└── tests/                          # 100 automated unit & integration tests (Pytest)
```

---

## 🛠️ Quickstart Guide

### 1. Pre-Flight Health Check (First Run)
Verify environment, directories, ports, and model integrity:
```bash
python scripts/doctor.py
```

### 2. Launch Desktop Hub (Linux / macOS / Development)
```bash
./scripts/start_dev.sh
```
- Open **`http://localhost:8000/client`** for the **Monitoring Client (SPA)**.
- Open **`http://localhost:8000/api/v1/system/diagnostics`** for **Subsystem Health Status**.
- Open **`http://localhost:8000/api/v1/system/hardware`** for **Hardware Silicon & Accelerators**.
- Open **`http://localhost:8000/docs`** for interactive Swagger REST API documentation.

### 3. Deploy on Windows 11 ARM64 (Snapdragon X Elite / Copilot+ PC)
Open PowerShell 7 as Administrator:
```powershell
# Automated setup (Python environment, PyTorch, ONNX, and directory structure)
.\scripts\install_windows.ps1

# Launch Hub in background
.\scripts\start_windows.ps1

# Query real-time subsystem health
.\scripts\health_windows.ps1

# Stop Hub background process
.\scripts\stop_windows.ps1
```

### 4. Run Automated Test Suite (100 Tests)
```bash
PYTHONPATH=. pytest -v
```

### 5. Run Hardware Silicon Benchmark
```bash
python scripts/validate_snapdragon_runtime.py
```

### 6. Run Complete Deterministic Demo
```bash
python scripts/run_demo.py
```

### 7. Run Android Camera Node
```bash
cd apps/camera
flutter run --release
```
- The phone discovers the Snapdragon PC over local Wi-Fi via mDNS (`_smart-spectator._tcp`).
- Enter the 6-digit PIN displayed on the PC dashboard to authenticate.
- Tap **"Start Streaming"** to begin transmitting 720p @ 30 FPS video to the Hub.
