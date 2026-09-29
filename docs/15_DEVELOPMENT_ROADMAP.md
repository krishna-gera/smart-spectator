# Smart Spectator — Multi-Phase Development Roadmap

**Document ID:** `SS-DOC-015`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Master Phasing Overview

The Smart Spectator engineering roadmap is partitioned into six distinct, milestone-driven phases. Each phase builds systematically on the architectural foundation established in Phase 0.

```
+------------------------------------------------------------------------------------+
|                               DEVELOPMENT TIMELINE                                 |
+------------------------------------------------------------------------------------+
|  Phase 0: Architecture, Technical Specs & Foundation Scaffolding    [ COMPLETED ]  |
|  Phase 1: Android Camera Node, Pairing & Low-Latency Streaming      [ NEXT ]       |
|  Phase 2: AI Ingestion, Level 1/2 Perception & Snapdragon NPU Base  [ UPCOMING ]   |
|  Phase 3: Smart Spectator Dataset & SpectatorNet Temporal Model     [ UPCOMING ]   |
|  Phase 4: Monitoring Tasks, ROI Zones, Event Engine & Dashboard     [ UPCOMING ]   |
|  Phase 5: Competition Hardening, NPU Benchmarks & Live Showcase      [ UPCOMING ]   |
|  Phase 6: Future Scale (RTSP/ONVIF CCTV, VLM Queries, iOS Node)     [ POST-COMP ]  |
+------------------------------------------------------------------------------------+
```

---

## 2. Phase-by-Phase Milestone Breakdown

### Phase 0: Architecture & Foundation (Current)
- [x] Complete technical specifications across all 18 master architectural documents.
- [x] Establish monorepo structure (`apps/`, `services/`, `ai/`, `shared/`).
- [x] Implement strongly-typed data contracts (`shared/schemas/v1/models.py`).
- [x] Implement hardware-agnostic protocols (`CameraSource`, `InferenceProvider`, `AIModel`).
- [x] Complete SQLite WAL database schema and entity design.
- [x] Freeze MVP boundaries and document Architectural Decision Records (ADRs).

---

### Phase 1: Core Networking & Streaming Pipeline
**Primary Objective:** Deliver a working video link between the Android phone and the Desktop Hub over local Wi-Fi.
- **Android Node (`apps/camera`):**
  - Implement Flutter UI shell with permission handling and camera preview.
  - Implement native Android `MediaCodec` H.264 hardware encoder pipeline.
  - Implement mDNS client discovery and 6-digit PIN pairing UI.
  - Implement battery and thermal telemetry reporter.
- **Desktop Hub (`services/hub_backend` & `services/stream_engine`):**
  - Implement FastAPI local server with mDNS service advertiser.
  - Implement device pairing service and SQLite token authentication.
  - Implement binary H.264 stream ingestion socket and FFmpeg frame demuxer.
  - Expose live MJPEG / WebSocket canvas stream to local web browser.

---

### Phase 2: AI Pipeline & Snapdragon NPU Acceleration
**Primary Objective:** Ingest frames into the perception pipeline with hardware-accelerated detection and tracking.
- **Inference Infrastructure (`ai/inference` & `services/ai_engine`):**
  - Implement `InferenceProvider` interface with `QNNInferenceProvider` (Qualcomm AI Engine Direct / ONNX Runtime QNN EP) and fallback providers (DirectML, CPU).
  - Deploy Level 1 Object Detector (YOLOv8-Nano) compiled for Snapdragon Hexagon NPU.
- **Tracking & Buffering:**
  - Implement Level 2 Object Tracker (ByteTrack) maintaining persistent track IDs.
  - Implement memory-bounded Circular Ring Buffer storing 15 seconds of rolling video.
  - Implement adaptive motion-gated frame sampler (skipping static scenes).

---

### Phase 3: Dataset Collection & SpectatorNet Temporal Model
**Primary Objective:** Train and deploy the custom temporal event intelligence model.
- **Data Engineering (`ai/datasets` & `ai/training`):**
  - Collect and annotate the 6,000-clip Smart Spectator Dataset across diversity axes.
  - Implement PyTorch training pipeline for SpectatorNet (MobileNetV3 backbone + BiGRU).
- **Optimization for Snapdragon NPU:**
  - Export PyTorch checkpoint to ONNX Opset 17.
  - Quantize to INT8 and compile using Qualcomm AI Hub CLI (`qai-hub compile & profile`).
  - Deploy compiled DLC / ONNX model into Level 3 AI perception engine.

---

### Phase 4: Monitoring Tasks, Event Engine & User Dashboard
**Primary Objective:** Enable user-defined monitoring policies, live alerting, and clip playback.
- **Event & Storage Subsystems (`services/event_engine` & `services/hub_backend`):**
  - Implement rule evaluator for `MonitoringTask` policies (object disappearance, zone intrusion).
  - Implement pre/post-roll MP4 clip synthesis from Circular Ring Buffer.
- **Client Application (`apps/client` & `apps/hub`):**
  - Build responsive multi-camera grid dashboard.
  - Implement interactive ROI polygon drawing tool on live camera view.
  - Implement real-time WebSocket event alert banner with video clip player.

---

### Phase 5: Competition Hardening & Snapdragon Showcase
**Primary Objective:** Polish presentation, benchmark metrics, and finalize packaging for evaluation.
- Conduct comparative benchmarks: Hexagon NPU vs. Adreno GPU vs. CPU (latency, FPS, watts, thermal).
- Build automated live telemetry overlay showcasing real-time NPU TOPS and inference latency.
- Create single-click installer scripts for Windows on ARM (Snapdragon PC) and macOS.
- Produce challenge presentation materials, system walkthrough video, and slide deck.

---

### Phase 6: Post-Competition Scalability
- Implement `RTSPCameraSource` and `ONVIFCameraSource` for legacy CCTV integration.
- Implement Level 4 Vision-Language Model interface for natural language query execution.
- Build iOS camera node client.
