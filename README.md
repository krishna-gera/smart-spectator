# Smart Spectator 👁️⚡

> **A Local-First Visual Intelligence Ecosystem for Snapdragon-Powered PCs and Repurposed Edge Nodes.**  
> Developed for the **Snapdragon AI Lab Build & Present Challenge**.

---

## 🌟 Project Vision

Smart Spectator turns everyday Android smartphones into high-definition, intelligent camera nodes orchestrated by a central **Snapdragon-powered Desktop Hub**. 

By offloading compute to the **45+ TOPS Qualcomm Hexagon NPU** on Snapdragon X-Series platforms, Smart Spectator delivers real-time spatial object detection, multi-object temporal tracking, and custom event reasoning (**SpectatorNet**) completely within the local network—with **zero cloud dependency, zero subscription costs, and guaranteed privacy**.

```
Android Camera Node
       ↓ (Low-latency H.264 over local Wi-Fi)
Smart Spectator Desktop Hub
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

## 📂 Repository Structure

The project is structured as a modular monorepo:

```
smart-spectator/
│
├── apps/
│   ├── camera/           # Android Camera Node (Flutter + CameraX/MediaCodec)
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
├── docs/                 # Master Phase 0 Technical Specifications (18 Documents)
│   ├── 01_SYSTEM_OVERVIEW.md
│   ├── 02_ARCHITECTURE.md
│   ├── 03_COMPONENT_ARCHITECTURE.md
│   ├── 04_NETWORK_ARCHITECTURE.md
│   ├── 05_CAMERA_PROTOCOL.md
│   ├── 06_DEVICE_AUTHENTICATION.md
│   ├── 07_API_SPECIFICATION.md
│   ├── 08_DATA_MODELS.md
│   ├── 09_AI_ARCHITECTURE.md
│   ├── 10_MODEL_STRATEGY.md
│   ├── 11_DATASET_STRATEGY.md
│   ├── 12_SNAPDRAGON_OPTIMIZATION.md
│   ├── 13_SECURITY_MODEL.md
│   ├── 14_FUTURE_CCTV_ARCHITECTURE.md
│   ├── 15_DEVELOPMENT_ROADMAP.md
│   ├── 16_DECISION_LOG.md
│   ├── 17_MVP_SCOPE.md
│   └── 18_PPT_ARCHITECTURE_NOTES.md
│
├── scripts/              # Setup, validation & benchmark automation
├── tests/                # Contract, unit & integration test suites
└── README.md
```

---

## 📑 Phase 0 Architecture Specifications

| Document | Focus Area |
| :--- | :--- |
| [01_SYSTEM_OVERVIEW.md](file:///Users/krishnagera/smart-spectator/docs/01_SYSTEM_OVERVIEW.md) | Executive vision, problem statement, and competition alignment. |
| [02_ARCHITECTURE.md](file:///Users/krishnagera/smart-spectator/docs/02_ARCHITECTURE.md) | High-level topology, modular monolith design, latency budget. |
| [03_COMPONENT_ARCHITECTURE.md](file:///Users/krishnagera/smart-spectator/docs/03_COMPONENT_ARCHITECTURE.md) | Subsystems: Camera Node, Desktop Hub, and Client details. |
| [04_NETWORK_ARCHITECTURE.md](file:///Users/krishnagera/smart-spectator/docs/04_NETWORK_ARCHITECTURE.md) | Dual-channel LAN transport, mDNS discovery, throughput budgets. |
| [05_CAMERA_PROTOCOL.md](file:///Users/krishnagera/smart-spectator/docs/05_CAMERA_PROTOCOL.md) | 24-byte binary video packet header, H.264 GOP, JSON control. |
| [06_DEVICE_AUTHENTICATION.md](file:///Users/krishnagera/smart-spectator/docs/06_DEVICE_AUTHENTICATION.md) | Local zero-trust pairing, 6-digit PIN verification, HMAC tokens. |
| [07_API_SPECIFICATION.md](file:///Users/krishnagera/smart-spectator/docs/07_API_SPECIFICATION.md) | OpenAPI 3.1 REST endpoints and WebSocket message channels. |
| [08_DATA_MODELS.md](file:///Users/krishnagera/smart-spectator/docs/08_DATA_MODELS.md) | SQLite WAL relational schemas, indices, and entity relationships. |
| [09_AI_ARCHITECTURE.md](file:///Users/krishnagera/smart-spectator/docs/09_AI_ARCHITECTURE.md) | Multi-tier perception: Detection, Tracking, and Temporal Event AI. |
| [10_MODEL_STRATEGY.md](file:///Users/krishnagera/smart-spectator/docs/10_MODEL_STRATEGY.md) | Custom SpectatorNet architecture, MobileNetV3 + BiGRU, QNN export. |
| [11_DATASET_STRATEGY.md](file:///Users/krishnagera/smart-spectator/docs/11_DATASET_STRATEGY.md) | Public dataset evaluation & 6,000-clip Smart Spectator Dataset plan. |
| [12_SNAPDRAGON_OPTIMIZATION.md](file:///Users/krishnagera/smart-spectator/docs/12_SNAPDRAGON_OPTIMIZATION.md) | Qualcomm Hexagon NPU targeting, QNN execution provider, fallback. |
| [13_SECURITY_MODEL.md](file:///Users/krishnagera/smart-spectator/docs/13_SECURITY_MODEL.md) | Threat matrix, memory safety, least privilege, local privacy. |
| [14_FUTURE_CCTV_ARCHITECTURE.md](file:///Users/krishnagera/smart-spectator/docs/14_FUTURE_CCTV_ARCHITECTURE.md) | Decoupled `CameraSource` abstraction for future RTSP/ONVIF CCTV. |
| [15_DEVELOPMENT_ROADMAP.md](file:///Users/krishnagera/smart-spectator/docs/15_DEVELOPMENT_ROADMAP.md) | Six-phase engineering milestones from Phase 0 to competition prep. |
| [16_DECISION_LOG.md](file:///Users/krishnagera/smart-spectator/docs/16_DECISION_LOG.md) | Architecture Decision Records (ADR-001 through ADR-012). |
| [17_MVP_SCOPE.md](file:///Users/krishnagera/smart-spectator/docs/17_MVP_SCOPE.md) | Strictly bounded MVP deliverables vs. deferred Phase 6 backlog. |
| [18_PPT_ARCHITECTURE_NOTES.md](file:///Users/krishnagera/smart-spectator/docs/18_PPT_ARCHITECTURE_NOTES.md) | Pitch deck narrative, live demo walkthrough script, judge FAQ defense. |

---

## 🛠️ Technology Stack & Hardware Acceleration

- **Camera Node (Android):** Flutter + Native Kotlin `MediaCodec` (H.264 Annex-B, 720p 30 FPS).
- **Desktop Hub Shell:** Flutter Desktop (Windows on ARM64 / macOS).
- **Hub Services Core:** Python 3.11+, FastAPI (Async REST / WebSockets), PyAV / FFmpeg.
- **Embedded Database:** SQLite 3 with Write-Ahead Logging (`WAL`).
- **AI Runtimes:** Qualcomm AI Engine Direct (QNN SDK), ONNX Runtime with `QNNExecutionProvider`, DirectML (Windows GPU), CoreML (macOS).
- **Perception:** YOLOv8-Nano (Spatial Detection), ByteTrack (Multi-Object Association), SpectatorNet (Custom Temporal Event Classifier).
