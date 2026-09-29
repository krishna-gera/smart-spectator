# Smart Spectator — MVP Scope & Feature Boundary

**Document ID:** `SS-DOC-017`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Frozen  

---

## 1. Scope Boundary Philosophy

To guarantee flawless execution, exceptional performance, and timely delivery for the **Snapdragon AI Lab Build & Present Challenge**, the scope of the Minimum Viable Product (MVP) is strictly bounded. 

All engineering effort during Phases 1–5 must concentrate on the core value proposition: **low-latency local camera nodes feeding a Snapdragon-powered PC running high-performance local AI perception and temporal event intelligence**.

```
+------------------------------------------------------------------------------------+
|                               MVP FEATURE MATRIX                                   |
+------------------------------------------------------------------------------------+
|  IN SCOPE (MVP - Phases 1 to 5)          |  OUT OF SCOPE (Deferred to Phase 6)     |
|------------------------------------------+-----------------------------------------|
|  - Android Camera Node (Flutter)         |  - Cloud backend / SaaS hosting         |
|  - Snapdragon PC Desktop Hub             |  - Remote WAN / Internet relay streaming|
|  - mDNS Zero-Config Discovery            |  - Physical RTSP / ONVIF CCTV hardware  |
|  - 6-Digit PIN Pairing & Auth            |  - Enterprise Multi-Tenant IAM / OAuth  |
|  - Low-Latency H.264 Ingest over LAN     |  - Facial Recognition / Biometrics      |
|  - Multi-Camera Tile Grid (1 to 4 cams)  |  - Voice Assistant / Audio Chatbot      |
|  - Level 1 Object Detection (YOLOv8n)    |  - Massive 7B+ Vision-Language Models   |
|  - Level 2 Multi-Object Tracking         |  - iOS Camera Node Application          |
|  - Level 3 Custom SpectatorNet Event AI  |  - PTZ Mechanical Motor Control         |
|  - Event Engine & ROI Polygon Logic      |  - Cellular LTE / 5G Fallback Streaming |
|  - Pre/Post Event Ring Buffer Recording  |  - Hardware Siren / Relay Actuators     |
|  - SQLite WAL Local Metadata Store       |                                         |
|  - Web/Mobile Responsive Dashboard       |                                         |
|  - Snapdragon NPU Optimization (QNN EP)  |                                         |
|  - Real-time Hardware Telemetry Display  |                                         |
+------------------------------------------------------------------------------------+
```

---

## 2. In-Scope MVP Functional Specifications

### 2.1 Android Camera Node (`apps/camera`)
- **Single-Screen Intuitive UI:** One-tap start/stop, viewfinder preview, active streaming indicator.
- **Pairing Flow:** Automated mDNS Hub discovery; manual 6-digit PIN input fallback.
- **Video Capture & Encoding:** Hardware-accelerated H.264 encoding via `MediaCodec` at 720p 30 FPS.
- **Background Persistence:** Android Foreground Service with continuous notification.
- **Telemetry Beacon:** 1 Hz reporting of battery %, charging state, thermal sensor, and encoder FPS.

### 2.2 Desktop Hub Core (`apps/hub` & `services/*`)
- **Platform Targets:** Windows 11 on ARM64 (Snapdragon X-Series) and macOS (Apple Silicon for local dev).
- **Service Orchestration:** Single local process (FastAPI + Flutter Desktop) with zero external database dependencies.
- **Stream Ingestion:** Up to 4 simultaneous 720p H.264 streams with hardware-accelerated decode.
- **Ring Buffer:** 15-second rolling pre-event frame buffer per camera in host memory.
- **Local Storage:** SQLite database for metadata; local directory for MP4 clips.

### 2.3 AI Pipeline & Event Engine
- **Hardware Acceleration:** Native execution on Snapdragon Hexagon NPU via Qualcomm AI Engine Direct (QNN Execution Provider).
- **Level 1 Detection:** Fast spatial detection running at 5 FPS per camera.
- **Level 2 Tracking:** ByteTrack spatial-temporal tracklet persistence.
- **Level 3 Custom Event Model:** SpectatorNet sliding-window classifier detecting `OBJECT_REMOVED`, `OBJECT_MOVED`, `PERSON_ENTERED`, `PERSON_LEFT`, and `CAMERA_BLOCKED`.
- **Monitoring Tasks:** UI configuration for monitoring targets (e.g. "Alert if bottle is removed from desk zone").
- **Event Recording:** Automatic export of 30-second clips ($T - 15\text{s}$ to $T + 15\text{s}$) upon event trigger.

### 2.4 Monitoring Dashboard (`apps/client`)
- **Live Multi-View:** 2x2 responsive camera grid with low latency ($< 150\text{ms}$).
- **Interactive ROI Editor:** Draw custom detection polygons directly over camera video feeds.
- **Event Alert Banner:** Instant toast notifications with event category badge and snapshot thumbnail.
- **Clip Reviewer:** Historical event list with built-in video player and scrub bar.
- **Snapdragon Telemetry Overlay:** Real-time display of NPU TOPS, inference latency (ms), and frame throughput.

---

## 3. Explicit Acceptance Criteria for MVP Completion

1. **End-to-End Pairing:** An Android phone discovers the Hub via mDNS and pairs within 15 seconds.
2. **Multi-Camera Concurrency:** 2 Android camera nodes stream 720p 30 FPS video simultaneously to the Hub without frame tearing or audio-video desync.
3. **Sub-10ms NPU Inference:** Level 1 object detection executes on the Snapdragon Hexagon NPU in under $10\text{ms}$ per frame.
4. **Reliable Event Trigger:** When a monitored object (e.g., mug or phone) is removed from a designated desk zone, an `OBJECT_REMOVED` event is emitted and displayed on the client within $500\text{ms}$.
5. **Clip Persistence:** The resulting event clip contains 15 seconds of video *prior* to the object removal and 15 seconds *after*, encoded as an MP4 file playable in the dashboard.
6. **Zero Cloud Dependency:** The entire system functions with the WAN / Internet cable disconnected from the Wi-Fi router.
