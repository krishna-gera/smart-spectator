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

## 🚀 Phase Status

- **Phase 0 (Architecture & Foundation):** ✅ **COMPLETED** (18 Master Specifications, Shared Protocols, Contracts)
- **Phase 1 (Core Streaming & Pairing):** ✅ **COMPLETED** (FastAPI Core, SQLite WAL, mDNS Discovery, 6-Digit PIN Pairing, Binary Framing Protocol, Live Preview, Android Camera App)
- **Phase 2 (AI Perception & Snapdragon NPU):** ⏳ *Next Milestone* (YOLOv8n on Hexagon NPU, ByteTrack, Circular Ring Buffer)

---

## 📂 Repository Structure

```
smart-spectator/
│
├── apps/
│   ├── camera/           # Android Camera Node (Flutter + CameraX)
│   ├── hub/              # Desktop Hub UI Shell (Flutter Desktop Windows/macOS)
│   └── client/           # Responsive Monitoring Client (Web / Mobile)
│
├── services/
│   ├── hub_backend/      # FastAPI local orchestrator, REST, WebSockets & Storage
│   ├── stream_engine/    # Hardware video ingestion, demuxer & circular ring buffers
│   ├── ai_engine/        # Multi-stage perception orchestrator & inference runtimes
│   ├── event_engine/     # State machines, ROI evaluation & policy triggers
│   └── device_manager/   # mDNS beacon, 6-digit PIN pairing & credential security
│
├── ai/
│   ├── models/           # Exported ONNX / Qualcomm QNN DLC model artifacts
│   ├── training/         # PyTorch pipelines for custom SpectatorNet model
│   ├── datasets/         # Manifests, annotations & tools for Smart Spectator Dataset
│   ├── evaluation/       # Accuracy, latency, and power benchmarking harnesses
│   └── inference/        # Hardware providers (Hexagon NPU, DirectML, CPU)
│
├── shared/
│   ├── schemas/v1/       # Versioned Pydantic data contracts (Device, Camera, Event, etc.)
│   ├── protocols/        # Hardware abstractions (CameraSource, InferenceProvider, AIModel)
│   └── constants/        # System ports, timeouts, default buffer configurations
│
├── docs/                 # Master Specifications & Implementation Reports
│   ├── PHASE_1_IMPLEMENTATION.md  # Detailed Phase 1 Implementation & Test Results
│   ├── 01_SYSTEM_OVERVIEW.md through 18_PPT_ARCHITECTURE_NOTES.md
│
├── scripts/
│   ├── setup_dev.sh      # Environment configuration script
│   └── test_stream_client.py # End-to-end camera-to-hub streaming verification
│
├── tests/                # Unit, integration & protocol test suites (Pytest)
└── README.md
```

---

## 🛠️ Quickstart Guide

### 1. Setup Local Environment
```bash
bash scripts/setup_dev.sh
```

### 2. Launch Desktop Hub
```bash
python3 -m uvicorn services.hub_backend.main:app --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser to view the **Live Hub Developer Dashboard**.

### 3. Run Automated Verification Tests
```bash
# Run 17 unit and integration tests
python3 -m pytest -v tests/

# Run end-to-end streaming simulation
python3 scripts/test_stream_client.py
```

### 4. Run Android Camera Node
```bash
cd apps/camera
flutter run
```
- The app automatically discovers the Hub on the local Wi-Fi via mDNS (`_smartspectator._tcp.local.`).
- Input the 6-digit verification code shown on the Desktop Hub dashboard.
- Tap **"Start Streaming"** to begin transmitting 720p @ 30 FPS video to the Hub.
