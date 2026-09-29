# Smart Spectator — System Architecture

**Document ID:** `SS-DOC-002`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. High-Level Architecture Topology

Smart Spectator follows a **Hub-and-Spoke Edge Architecture** optimized for local networks. The system strictly avoids cloud-hosted microservices in favor of an efficient, low-overhead **Modular Monolith** running locally on the user's Snapdragon PC.

```
                    +-------------------------------------------------------------+
                    |                      LOCAL WI-FI (LAN)                      |
                    +-------------------------------------------------------------+
                                       |                                   ^
            Raw Video Stream           |                                   |  Dashboard View
         (H.264 over TCP/WebSocket)    |                                   |  Task Configuration
            Telemetry & Control (WS)   |                                   |  REST / WebSocket
                                       v                                   |
             +----------------------------------+            +----------------------------+
             |      SMART SPECTATOR HUB         |            |   SMART SPECTATOR CLIENT   |
             |   (Snapdragon-Powered PC)        |            |   (Web Browser / Desktop)  |
             +----------------------------------+            +----------------------------+
             |                                  |
             |  1. Device Discovery & Auth      |
             |  2. Video Ingestion & Decoder    |
             |  3. Circular Ring Buffer         |
             |  4. Inference Orchestrator       |
             |     - Snapdragon Hexagon NPU     |
             |  5. Level 1: Object Detection    |
             |  6. Level 2: Multi-Obj Tracking  |
             |  7. Level 3: SpectatorNet Event  |
             |  8. Event & Monitoring Engine    |
             |  9. SQLite WAL Data Store        |
             | 10. Local FastApi Gateway        |
             |                                  |
             +----------------------------------+
                               ^
                               |
         +---------------------+---------------------+
         |                                           |
+------------------+                       +-------------------+
|  Phone Camera 1  |                       |  Phone Camera N   |
| (Android Node)   |                       | (Android Node)    |
+------------------+                       +-------------------+
```

---

## 2. End-to-End Data Flow Pipeline

The end-to-end processing pipeline transforms physical light at the camera lens into structured intelligence and action:

```
[ Camera Sensor ]
       | (30 FPS raw NV21/YUV420)
[ MediaCodec Hardware Encoder ]
       | (H.264 Annex-B NAL units)
[ Network Transport (TCP/WS) ]
       | (Sub-20ms LAN transit)
[ Hub Stream Ingestion & Demuxer ]
       |
       +---> [ Circular Video Ring Buffer ] (Stores uncompressed/compressed 15s pre-roll)
       |
[ Hardware Video Decoder (FFmpeg/DirectX/VideoToolbox) ]
       | (Decoded BGR24 Frames)
[ Adaptive Frame Sampler ] (Decimates 30 FPS -> 5 FPS per stream)
       |
[ Inference Provider (Snapdragon NPU / QNN EP) ]
       |
       v
[ Level 1: Spatial Detection (YOLOv8-Nano) ]
       | (Bounding boxes, class IDs, confidences)
       v
[ Level 2: Temporal Object Tracker (ByteTrack) ]
       | (Persistent Track IDs, trajectory vectors, velocity)
       v
[ Level 3: SpectatorNet Temporal Event Model ]
       | (Temporal feature embeddings + GRU state transition)
       v
[ Event Engine & Monitoring Task Evaluator ]
       |
       +---> [ Trigger Match? ]
                  |
                  +--- YES ---> [ Event Dispatcher ]
                  |                   |
                  |                   +---> [ Ring Buffer Clip Generator ] (Extracts -15s to +15s to MP4)
                  |                   +---> [ SQLite Database Persistence ] (Stores Event & Clip metadata)
                  |                   +---> [ WebSocket Broadcast to Clients ] (Immediate visual alert)
                  |
                  +--- NO  ---> [ Discard / Update Scene State Cache ]
```

---

## 3. Modular Monolith Architecture for Desktop Hub

Rather than deploying distributed microservices requiring Docker, Kubernetes, and inter-process RPC overhead on a personal computer, the Smart Spectator Hub runs as a single, multi-threaded, highly optimized process with cleanly isolated domains:

```
+------------------------------------------------------------------------------------+
|                         SMART SPECTATOR DESKTOP HUB CORE                           |
+------------------------------------------------------------------------------------+
|                                                                                    |
|  +-----------------------+  +-----------------------+  +------------------------+  |
|  |  Device Manager       |  |  Stream Engine        |  |  AI Engine             |  |
|  |  - mDNS Beacon        |  |  - Network Receivers  |  |  - InferenceProvider   |  |
|  |  - Pairing Auth       |  |  - Hardware Decoder   |  |  - Level 1: Detector   |  |
|  |  - Heartbeat & Health |  |  - Ring Buffers       |  |  - Level 2: Tracker    |  |
|  |  - Token Store        |  |  - Frame Sampler      |  |  - Level 3: Event Net  |  |
|  +-----------------------+  +-----------------------+  +------------------------+  |
|              |                          |                           |              |
|              +--------------------------+---------------------------+              |
|                                         v                                          |
|  +------------------------------------------------------------------------------+  |
|  |                           Event & Decision Engine                            |  |
|  |  - Rule Evaluator          - Monitoring Task State Machine                   |  |
|  |  - Zone / ROI Logic        - Clip Persistence Trigger                        |  |
|  +------------------------------------------------------------------------------+  |
|                                         |                                          |
|              +--------------------------+---------------------------+              |
|              v                                                      v              |
|  +-----------------------+                             +------------------------+  |
|  |  Storage Layer        |                             |  API & Gateway         |  |
|  |  - SQLite (WAL Mode)  |                             |  - FastAPI Async REST  |  |
|  |  - Clip File System   |                             |  - WebSocket Broadcast |  |
|  |  - Snapshots          |                             |  - Static Web Host     |  |
|  +-----------------------+                             +------------------------+  |
+------------------------------------------------------------------------------------+
```

---

## 4. Architectural Principles

1. **Local-First & Zero-Cloud Dependency:** The system must install and run 100% offline. No telemetry, account registration, or external APIs are required for full functionality.
2. **Strict Hardware Abstraction:** Business logic and AI models must never directly invoke OS-specific APIs. All camera sources implement `CameraSource`; all compute backends implement `InferenceProvider`.
3. **Decoupled Perception Stages:** Spatial detection, temporal tracking, and event classification are distinct architectural stages. Changing an object detector from YOLOv8 to another model never affects the Event Engine.
4. **Non-Blocking Zero-Copy Video Pipeline:** The streaming and recording subsystem runs in dedicated native threads with shared memory frame ring buffers to prevent Python GIL contention.
5. **Deterministic Event Recording:** Rather than recording 24/7 (which exhausts local consumer SSDs), the system maintains a rolling in-memory/scratch disk ring buffer. Recordings are synthesized on-demand with retroactive pre-event buffers.
6. **Graceful Fault Degradation:** If the Qualcomm NPU is saturated, inference dynamically falls back to Adreno GPU (DirectML) or CPU, and sampling rate is automatically throttled to preserve host stability.

---

## 5. Latency & Resource Budget

To ensure a smooth user experience on Snapdragon X-series laptops and desktop stations, the following performance budgets are established:

| Pipeline Stage | Target Latency Budget | Maximum Permissible |
| :--- | :--- | :--- |
| Android Camera Sensor Capture & Encode | $16\text{ ms}$ | $33\text{ ms}$ |
| LAN Transit (5GHz Wi-Fi / GbE) | $8\text{ ms}$ | $25\text{ ms}$ |
| Stream Ingestion & HW Decoding | $12\text{ ms}$ | $25\text{ ms}$ |
| Frame Preprocessing & Tensor Normalization | $4\text{ ms}$ | $8\text{ ms}$ |
| NPU Inference (Level 1: YOLOv8n @ 640x640) | $6\text{ ms}$ | $12\text{ ms}$ |
| Object Tracking (ByteTrack) | $2\text{ ms}$ | $5\text{ ms}$ |
| Event Model Inference (SpectatorNet) | $8\text{ ms}$ | $15\text{ ms}$ |
| Event Engine Evaluation & Clip Trigger | $2\text{ ms}$ | $5\text{ ms}$ |
| WebSocket Alert Delivery to Client | $5\text{ ms}$ | $15\text{ ms}$ |
| **Total Glass-to-Alert Latency** | **$63\text{ ms}$** | **$< 150\text{ ms}$** |
