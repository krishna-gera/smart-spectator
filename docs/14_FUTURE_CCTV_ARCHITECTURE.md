# Smart Spectator — Future Camera Compatibility Architecture

**Document ID:** `SS-DOC-014`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  
**Notice:** Architecture and Abstraction ONLY. DO NOT IMPLEMENT CCTV/RTSP/ONVIF IN MVP.  

---

## 1. The Universal Source Philosophy

A critical architectural requirement of Smart Spectator is that **downstream perception engines, tracking algorithms, temporal reasoning models, and client dashboards must be 100% agnostic to physical camera hardware and transport protocols**.

Whether a video frame originates from an Android smartphone, an industrial ONVIF PTZ security camera, an RTSP commercial CCTV stream, or a local USB webcam, the processing pipeline interacts solely through the unified `CameraSource` interface.

```
+------------------------------------------------------------------------------------+
|                             PLUGGABLE CAMERA SOURCES                               |
+------------------------------------------------------------------------------------+
|                                                                                    |
|  +--------------------+  +--------------------+  +--------------------+            |
|  | PhoneCameraSource  |  |  RTSPCameraSource  |  | ONVIFCameraSource  |  ... (USB) |
|  | (Phase 1 Impl)     |  | (Future Phase 2)   |  | (Future Phase 2)   |            |
|  +---------+----------+  +---------+----------+  +---------+----------+            |
|            |                       |                       |                       |
|            +-----------------------+-----------------------+                       |
|                                    v                                               |
|                    +-------------------------------+                               |
|                    |     CameraSource Interface    |                               |
|                    |   (shared/protocols/...py)    |                               |
|                    +---------------+---------------+                               |
|                                    |                                               |
+------------------------------------|-----------------------------------------------+
                                     v Normalized RGB/BGR Frame Arrays + Metadata
+------------------------------------------------------------------------------------+
|                        COMMON DOWNSTREAM INTELLIGENCE CORE                         |
|   - Circular Ring Buffer                                                           |
|   - Adaptive Frame Sampler & Motion Gating                                         |
|   - Level 1: Spatial Object Detector (Hexagon NPU)                                 |
|   - Level 2: Multi-Object Tracker (ByteTrack)                                      |
|   - Level 3: SpectatorNet Temporal Event Model                                     |
|   - Event Engine & Monitoring Task Evaluator                                       |
|   - SQLite WAL Metadata & MP4 Clip Generator                                       |
|   - Real-time Client Dashboard & Alert Dispatch                                    |
+------------------------------------------------------------------------------------+
```

---

## 2. Pluggable Source Implementations

### 2.1 `PhoneCameraSource` (Phase 1 Baseline)
- **Transport:** H.264 over TCP/WebSocket binary framing + JSON WebSocket control channel.
- **Hardware:** Android smartphone running `apps/camera`.
- **Special Capabilities:** Battery monitoring, thermal watchdog, remote flash/torch control, front/back lens switching.

### 2.2 `RTSPCameraSource` (Future Extensibility)
- **Transport:** Real-Time Streaming Protocol (`rtsp://<user>:<pass>@<ip>:<port>/stream1`) via TCP interleaved RTP packets.
- **Ingestion:** Managed via PyAV / FFmpeg native demuxer.
- **Protocol Features:** RTSP `DESCRIBE`, `SETUP`, `PLAY`, `TEARDOWN`, Digest Authentication (RFC 2617).

### 2.3 `ONVIFCameraSource` (Future Extensibility)
- **Transport:** ONVIF Profile S (Streaming) & Profile T (Advanced Video).
- **Discovery:** WS-Discovery (`SOAP-over-UDP` multicast on `239.255.255.250:3702`).
- **Capabilities:** Automated camera discovery on LAN, PTZ (Pan-Tilt-Zoom) preset controls, infrared night mode toggling.

### 2.4 `USBCameraSource` (Future Extensibility)
- **Transport:** Local DirectShow (Windows) / AVFoundation (macOS) / V4L2 (Linux).
- **Hardware:** USB webcams, UVC capture cards, embedded laptop webcams.
- **Capabilities:** Direct frame grab with zero network latency.

---

## 3. Contractual Decoupling Guarantees

By strictly enforcing the `CameraSource` contract:
1. **Zero Core Rewrites:** Adding industrial CCTV support in future releases will require writing **only one new class** (`RTSPCameraSource`) implementing the 7 abstract methods of `CameraSource`.
2. **AI Stability:** The Snapdragon AI Engine, model weights, and inference pipelines remain completely untouched when adding new camera sources.
3. **Unified Client Experience:** The monitoring dashboard displays live tiles, triggers tasks, and persists clips identically regardless of camera source type.
