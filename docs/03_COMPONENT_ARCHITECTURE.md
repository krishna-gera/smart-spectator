# Smart Spectator — Component Architecture

**Document ID:** `SS-DOC-003`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Component Hierarchy Overview

Smart Spectator consists of three primary software tiers:
1. **Camera Nodes (`apps/camera`)**: Android application built with Flutter and native CameraX/MediaCodec plugins.
2. **Desktop Hub (`apps/hub` & `services/*`)**: Snapdragon-optimized core running a Flutter Desktop UI paired with a high-performance Python/FastAPI local services engine.
3. **Monitoring Client (`apps/client`)**: Cross-platform Web/Mobile monitoring client for real-time video observation, alerts, and task orchestration.

```
+----------------------------------------------------------------------------------------------------+
|                                    SMART SPECTATOR ECOSYSTEM                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ ANDROID CAMERA NODE ]                  [ DESKTOP HUB ]                   [ MONITORING CLIENT ]  |
|  - Flutter UI Presentation                - Flutter Desktop UI Shell        - Flutter Web / React  |
|  - CameraX / NDK Pipeline                 - FastAPI Gateway                 - WebSocket Client     |
|  - Hardware H.264 Encoder                 - Stream Engine (C++/PyAV)        - Live Video Canvas    |
|  - mDNS Beacon                            - Device Manager                  - Event Feed & Timeline|
|  - Battery / Thermal Telemetry            - AI Perception Orchestrator      - Task Config Wizard   |
|  - Reconnect Controller                   - Hexagon NPU Provider            - Clip Video Player    |
|                                           - Event Decision Engine                                  |
|                                           - SQLite WAL Database                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Component A: Android Camera Application (`apps/camera`)

### 2.1 Role & Responsibilities
The Android device operates strictly as a **lightweight, high-reliability video capture node**. It does not perform heavy AI perception or store local clips, ensuring minimal battery consumption, zero thermal throttling, and sustained 24/7 uptime.

### 2.2 Internal Subsystems
```
+-----------------------------------------------------------------------------+
|                        ANDROID CAMERA NODE ARCHITECTURE                     |
+-----------------------------------------------------------------------------+
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  |                        Flutter UI / State Layer                       |  |
|  |  - Pairing Screen     - QR / Code Input     - Viewfinder Overlay      |  |
|  |  - Stream Metrics     - Thermal Warning     - Background Service Ctrl |  |
|  +-----------------------------------+-----------------------------------+  |
|                                      |                                      |
|  +-----------------------------------+-----------------------------------+  |
|  |                      Native Android Platform Layer                    |  |
|  |                                                                       |  |
|  |  +---------------------+  +--------------------+  +----------------+  |  |
|  |  | CameraX Capture API |  | MediaCodec HW Enc  |  | Telemetry Mon  |  |  |
|  |  | - NV21/YUV420 Buff  |  | - H.264 Baseline   |  | - Battery %    |  |  |
|  |  | - Auto-Exposure     |  | - 720p / 1080p     |  | - Temp (C)     |  |  |
|  |  | - Lens Facing       |  | - Bitrate Adapter  |  | - Wi-Fi RSSI   |  |  |
|  |  +----------+----------+  +---------+----------+  +--------+-------+  |  |
|  |             |                       |                      |          |  |
|  |             +------------+----------+                      |          |  |
|  |                          v                                 |          |  |
|  |               +----------------------+                     |          |  |
|  |               |  Network Transport   |<--------------------+          |  |
|  |               |  - H.264 NAL Sender  |                                |  |
|  |               |  - JSON WS Control   |                                |  |
|  |               +----------+-----------+                                |  |
|  +--------------------------|--------------------------------------------+  |
+-----------------------------|-----------------------------------------------+
                              v (Local Wi-Fi Network)
```

### 2.3 Operational Safeguards
1. **WakeLock & Foreground Service:** Runs a sticky Android Foreground Service with continuous audio-less notification to prevent OS sleep.
2. **Thermal Watchdog:** Monitors `BatteryManager.EXTRA_TEMPERATURE`. If battery temperature exceeds $42^\circ\text{C}$, the node drops target FPS from 30 to 15 and bitrate from 2500 kbps to 1000 kbps. If temperature exceeds $46^\circ\text{C}$, streaming is suspended to protect device battery longevity.
3. **Adaptive Bitrate Controller:** Monitors TCP packet acknowledgment times; scales resolution and bitrate dynamically upon network congestion.
4. **Auto-Reconnection Loop:** Exponential backoff ($1\text{s}, 2\text{s}, 4\text{s}, \dots, 30\text{s}$) upon network drops or hub restart.

---

## 3. Component B: Smart Spectator Desktop Hub (`apps/hub` & `services/*`)

The Desktop Hub is the intelligent core of the ecosystem. It is composed of five distinct service modules orchestrated into a cohesive local monolith:

```
+------------------------------------------------------------------------------------+
|                         SMART SPECTATOR DESKTOP HUB CORE                           |
+------------------------------------------------------------------------------------+
|                                                                                    |
|  +------------------------------------------------------------------------------+  |
|  |                   Presentation Layer: Flutter Desktop UI                     |  |
|  |  - Multi-Camera Tile Grid  - System Resource Gauges  - Event Log & Playback  |  |
|  +--------------------------------------+---------------------------------------+  |
|                                         | IPC / REST / WebSocket                   |
|  +--------------------------------------v---------------------------------------+  |
|  |                 FastAPI Application Gateway & Web Server                     |  |
|  +------------------------------------------------------------------------------+  |
|        |                  |                       |                  |             |
|        v                  v                       v                  v             |
|  +-----------+     +--------------+       +---------------+   +-----------------+  |
|  |  Device   |     |    Stream    |       |   AI Engine   |   |  Event Engine   |  |
|  |  Manager  |     |    Engine    |       | (Orchestrator)|   |  & Evaluator    |  |
|  +-----+-----+     +-------+------+       +-------+-------+   +--------+--------+  |
|        |                   |                      |                    |           |
|        v                   v                      v                    v           |
|  +------------------------------------------------------------------------------+  |
|  |                  Storage Engine (SQLite WAL & MP4 Ring Buffer)               |  |
|  +------------------------------------------------------------------------------+  |
+------------------------------------------------------------------------------------+
```

### 3.1 Device Manager (`services/device_manager`)
- Emits mDNS beacons (`_smartspectator._tcp.local.`) for auto-discovery.
- Handles pairing requests, generates 6-digit one-time tokens, and mints cryptographically signed device credentials.
- Maintains device registry, connectivity status, and node telemetry (battery, temperature, Wi-Fi signal).

### 3.2 Stream Engine (`services/stream_engine`)
- Manages incoming TCP/WebSocket video streams.
- Encapsulates hardware-accelerated video decoding via FFmpeg/PyAV.
- Maintains an in-memory **Circular Ring Buffer** holding the most recent 15 seconds of raw/encoded frames per active camera.
- Exposes decoupled `CameraSource` interfaces to the downstream pipeline.

### 3.3 AI Engine (`services/ai_engine`)
- Houses the `InferenceProvider` abstraction layer, executing models across Snapdragon Hexagon NPU, Adreno GPU (DirectML/CoreML), or CPU.
- Orchestrates multi-stage perception:
  - **Level 1:** Object Detection (e.g. YOLOv8n) running at 5 FPS per stream.
  - **Level 2:** Multi-Object Tracking (ByteTrack) maintaining spatial-temporal identity.
  - **Level 3:** SpectatorNet Temporal Event Model evaluating sequential feature states.

### 3.4 Event & Decision Engine (`services/event_engine`)
- Evaluates spatial-temporal observations against user-defined `MonitoringTask` policies.
- Computes zone intrusions, dwell times, object disappearances/removals, and scene obstructions.
- Dispatches event notifications to connected clients and signals the Stream Engine to persist the corresponding video clip.

### 3.5 Storage Layer (`services/hub_backend/storage`)
- **Metadata Database:** SQLite configured in Write-Ahead-Logging (WAL) mode for concurrent high-throughput writes.
- **Media Storage:** Structured directory hierarchy organizing event clips (`/recordings/YYYY-MM-DD/<event_id>.mp4`) and camera snapshot thumbnails (`/snapshots/<camera_id>.jpg`).

---

## 4. Component C: Smart Spectator Client (`apps/client`)

### 4.1 Role & Responsibilities
Provides the user interface for live multi-camera monitoring, interactive task setup, historical event review, and system diagnostic observation. It can run as:
- A local browser tab served directly by the Hub (`http://localhost:8000`).
- A mobile/tablet browser on the local Wi-Fi network (`http://<hub-ip>:8000`).
- A compiled cross-platform Flutter application.

### 4.2 Key Features
1. **Dynamic Grid View:** Responsive 1x1, 2x2, or 3x3 low-latency video matrix rendered via HTML5 Canvas / WebSocket JSMpeg / WebRTC.
2. **Interactive Zone Definition:** Interactive polygon drawing tool allowing users to define Regions of Interest (ROI) directly over the camera feed.
3. **Natural Task Configurator:** Structured UI for creating monitoring rules (e.g., Target: "Bottle", Action: "Alert if moved or removed", Zone: "Desk").
4. **Event Timeline & Player:** Chronological visual timeline with video scrubbing, event type badges, and clip download.
5. **Real-time Diagnostics Bar:** Displays live Snapdragon NPU TOPS, inference FPS, CPU/RAM usage, and camera node battery health.
