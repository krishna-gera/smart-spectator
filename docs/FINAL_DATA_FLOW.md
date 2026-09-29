# Smart Spectator — End-to-End System Data Flow Specification

**Document ID:** SS-DOC-028  
**Version:** 1.2.0  
**Phase:** 9 (Polished Intelligent Local Monitoring Product)  
**Status:** Certified Specification  

---

## 1. Architectural Overview

Smart Spectator transforms consumer Android smartphones into high-performance visual intelligence nodes paired with a Snapdragon-powered edge hub over private local Wi-Fi. The entire pipeline operates with **zero cloud dependencies** and **sub-100ms** processing latencies.

```
+---------------------------------------------------------------------------------------------------+
|                                      ANDROID CAMERA NODE                                          |
|                                                                                                   |
|  [ Camera Sensor ] ---> [ CameraX Preview ] ---> [ MediaCodec H.264 Encoder ]                    |
|       (1080p/720p)             (YUV_420_888)            (720p @ 30 FPS, Baseline/Main, CBR)       |
|                                                                 |                                 |
|                                                                 v                                 |
|  [ Local TCP Socket ] <-------------------------- [ Smart Spectator Packetizer ]                  |
|     (Port 8554 egress)                                   (0x53530001 Header + Payload + CRC32)     |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                    [ Wi-Fi LAN / 802.11ac/ax ]
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  SNAPDRAGON EDGE HUB (PC)                                         |
|                                                                                                   |
|  [ Stream Engine: TCP Ingest (Port 8554) ] ---> [ Reassembly & CRC32 Validation ]                 |
|                                                                 |                                 |
|                                                                 v                                 |
|  [ PyAV / FFmpeg H.264 Decoder ] <------------------------------+                                 |
|       (Decoded RGB / BGR Frames)                                                                  |
|               |                                                                                   |
|               +----------------------------+                                                      |
|               |                            |                                                      |
|               v                            v                                                      |
|  [ Circular Frame Buffer ]      [ Adaptive Frame Sampler ]                                        |
|   (Pre-roll: 5s / 150 frames)    (Motion-Gated Decimation: 5-10 FPS)                             |
|               |                            |                                                      |
|               |                            v                                                      |
|               |                 [ Level 1: YOLOv8n ONNX ]                                         |
|               |                  (Tensor: [1, 3, 640, 640] float32)                               |
|               |                            |                                                      |
|               |                            v                                                      |
|               |                 [ Level 2: ByteTrack ]                                            |
|               |                  (Hungarian Matching + Kalman Filter)                             |
|               |                            |                                                      |
|               |                            v                                                      |
|               |                 [ Observation Builder ]                                           |
|               |                  (Observation Schema: Detections + Active Tracks)                 |
|               |                            |                                                      |
|               |                            v                                                      |
|               |                 [ Level 3: SpectatorNet GRU ]                                     |
|               |                  (Tensor: [1, 16, 64] float32 / INT8)                             |
|               |                            |                                                      |
|               |                            v                                                      |
|               |                 [ Event Engine Evaluator ]                                        |
|               |                  (Spatial Polygons + Temporal Rules State Machine)                |
|               |                            |                                                      |
|               +----------------------------+                                                      |
|               | (On Event Trigger)                                                                |
|               v                                                                                   |
|  [ MP4 Clip Generator ]                                                                           |
|   (Pre-roll + Active + Post-roll -> recordings/event_<id>.mp4)                                    |
|               |                                                                                   |
|               +----------------------------+-----------------------------+                        |
|               |                            |                             |                        |
|               v                            v                             v                        |
|     [ SQLite Database ]         [ WebSocket Broadcaster ]     [ REST System APIs ]                |
|     (Events, Zones, Devices)     (ws://<hub-ip>:8000/api/v1)   (http://<hub-ip>:8000/api/v1)      |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                    MONITORING CLIENT / UI                                         |
|                                                                                                   |
|  * Real-Time Stream Preview (MJPEG/Canvas)    * Live Temporal Event Feed                          |
|  * Interactive Polygonal Zone Editor          * MP4 Clip Playback & System Diagnostics Dashboard  |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Detailed Data Transformation Across All 16 Pipeline Stages

### Stage 1: Camera Sensor Capture (Android)
- **Component:** Physical CMOS image sensor via Android Camera2 / CameraX API.
- **Data Format:** Sensor raw bayer transformed into Android `ImageFormat.YUV_420_888`.
- **Resolution:** Default 1280x720 (720p) @ 30 FPS (configurable to 1920x1080).
- **Color Space:** Rec. 601 / Rec. 709 YUV planar.

### Stage 2: Hardware Video Encoding
- **Component:** `MediaCodec` hardware encoder (Qualcomm Adreno / MediaTek / Exynos video engine).
- **Codec:** H.264 / AVC (Advanced Video Coding), Baseline or Main profile.
- **Keyframe Interval (GOP):** 1 keyframe per second (every 30 frames).
- **Bitrate:** CBR 2.0 Mbps (Adaptive degradation down to 800 kbps under Wi-Fi latency spikes).
- **Output:** Annex B NAL units (SPS `0x67`, PPS `0x68`, IDR `0x65`, non-IDR slices `0x61` or `0x41`).

### Stage 3: Smart Spectator Binary Packetizer
- **Component:** Native protocol packager (`ProtocolPacket.encode`).
- **Wire Format (24-Byte Header + Variable Payload + CRC32):**
  ```
  Offset  Bytes  Field Name        Type     Description
  0       4      magic             uint32   0x53530001 (ASCII "SS\0\1")
  4       1      version           uint8    0x01
  5       1      packet_type       uint8    0x01 = Frame, 0x02 = IDR, 0x03 = Heartbeat
  6       2      reserved          uint16   0x0000
  8       4      sequence_number   uint32   Monotonically incrementing (0 to 2^32-1)
  12      8      timestamp_us      uint64   Microseconds since UNIX epoch
  20      4      payload_size      uint32   Byte length of NAL payload
  24      N      payload           bytes    H.264 NAL stream
  24+N    4      crc32             uint32   IEEE 802.3 32-bit checksum
  ```

### Stage 4: Wi-Fi LAN Ingestion
- **Transport:** Persistent TCP socket stream.
- **Destination:** Hub IP address, port `8554` (configurable).
- **QoS:** Low-latency socket options (`TCP_NODELAY = 1`, buffer size = 256 KB).

### Stage 5: Packet Reassembly & Verification
- **Component:** `services.stream_engine.server.StreamEngine`.
- **Validation:**
  - Header magic matches `0x53530001`.
  - Protocol version matches `1`.
  - CRC32 checksum computed across header + payload matches trailing checksum bytes.
  - Gap detection: flags dropped packets when `seq != expected_seq`.

### Stage 6: Video Decoding
- **Component:** PyAV / FFmpeg bindings (`av.CodecContext.create('h264', 'r')`).
- **Input:** Clean NAL units parsed from incoming packets.
- **Output:** Decoded RGB24 / BGR24 NumPy arrays: `ndarray(shape=(720, 1280, 3), dtype=uint8)`.

### Stage 7: Adaptive Frame Sampling & Motion Gating
- **Component:** `services.ai_engine.frame_sampler.AdaptiveFrameSampler`.
- **Operation:**
  - Decimates incoming 30 FPS stream down to target 5–10 FPS.
  - Computes inter-frame luminance delta (motion gate).
  - Skips inference on static backgrounds, dropping CPU/NPU consumption by >65%.

### Stage 8: Level 1 Spatial Object Detection (YOLOv8n)
- **Component:** `services.ai_engine.detector.YOLOObjectDetector`.
- **Input Preprocessing:**
  - Letterbox resize to `640x640` with aspect-ratio preserving padding (fill color: 114).
  - BGR -> RGB conversion, normalization to `[0.0, 1.0]`.
  - Layout: `NCHW` float32 tensor of shape `(1, 3, 640, 640)`.
- **Execution:** ONNX Runtime via Hexagon QNN NPU / DirectML / CoreML / CPU.
- **Raw Output:** Tensor of shape `(1, 84, 8400)` representing `[cx, cy, w, h, class_probs...]`.
- **Postprocessing:**
  - Non-Maximum Suppression (NMS) with IoU threshold `0.45`, confidence threshold `0.35`.
  - Coordinates normalized to `[0.0, 1.0]` as `[x_min, y_min, x_max, y_max]`.

### Stage 9: Level 2 Multi-Object Tracking (ByteTrack)
- **Component:** `services.ai_engine.tracker.ByteTrackTracker`.
- **Operation:**
  - Two-stage association using Kalman Filter state prediction and Hungarian Algorithm on IoU distances.
  - Tracks persistent spatial trajectories across camera frames.
  - Emits `TrackedObject` records containing `track_id`, `class_name`, `bbox_xyxy`, `velocity_vector`, and `trajectory_history`.

### Stage 10: Observation Assembly
- **Component:** `services.ai_engine.observation_builder.ObservationBuilder`.
- **Schema:** Standardized `Observation` object:
  ```json
  {
    "camera_id": "cam_01",
    "timestamp": 1727654400.123,
    "frame_index": 450,
    "detections": [...],
    "tracked_objects": [...],
    "inference_telemetry": {
      "detector_model": "yolov8n",
      "backend": "gpu_coreml",
      "detection_ms": 3.38,
      "tracking_ms": 0.42,
      "total_ai_latency_ms": 3.80,
      "inference_fps": 286.9
    }
  }
  ```

### Stage 11: Level 3 Temporal Intelligence (SpectatorNet)
- **Component:** `ai.spectatornet.model.SpectatorNet`.
- **Input Preprocessing:**
  - Encodes 16-frame sliding observation window into `(1, 16, 64)` temporal feature tensor.
  - Features capture track velocities, class counts, spatial centroids, and motion dynamics.
- **Execution:** Evaluated in 0.25ms (INT8 quantized) on Snapdragon Hexagon NPU / CoreML.
- **Output:** Categorical probability distribution across 6 behavioral classes:
  - `NORMAL_ACTIVITY`
  - `PERSON_ENTERED`
  - `LOITERING`
  - `OBJECT_LEFT`
  - `RAPID_MOTION`
  - `CAMERA_BLOCKED`

### Stage 12: Event Engine State Machine & Rule Evaluation
- **Component:** `services.event_engine.engine.EventEngine`.
- **Evaluation:**
  - Point-in-polygon containment test for tracked objects against user-defined spatial `Zone` definitions.
  - Threshold comparison against active `EventRule` criteria (confidence, duration, loitering timeout).
  - Emits `Event` entities with state machine transitions: `detected -> active -> resolved`.

### Stage 13: MP4 Clip Recording & Ring Buffer Slicing
- **Component:** `services.event_engine.recording.RecordingManager`.
- **Operation:**
  - Reads pre-roll video frames from 5-second circular in-memory buffer.
  - Captures active event frames and post-roll duration (default: 5 seconds).
  - Encodes MP4 container using H.264 video codec.
  - Writes to disk: `recordings/event_<event_id>.mp4`.

### Stage 14: Local Database Persistence
- **Component:** SQLite 3 in WAL (Write-Ahead Logging) mode.
- **Schema:**
  - `devices`: Pairing records, authenticated tokens, device health.
  - `cameras`: Assigned camera streams, status, resolution.
  - `zones`: Polygonal boundary definitions (normalized `[x, y]` coordinates).
  - `event_rules`: Logic triggers, target classes, thresholds.
  - `events`: Historical event log, confidence scores, summaries, clip file paths.
  - `audit_logs`: Append-only tamper-evident audit trail.

### Stage 15: WebSocket & REST API Distribution
- **Component:** FastAPI Hub backend.
- **WebSockets:**
  - `/api/v1/events/ws`: Real-time push of newly triggered and resolved events.
  - `/api/v1/control/ws`: Bidirectional camera control and telemetry channel.
- **REST Endpoints:** Query historical clips, audit logs, system diagnostics, and hardware capabilities.

### Stage 16: Monitoring Client Presentation
- **Component:** Single-Page Web Application (`services/hub_backend/client/`).
- **Visualizations:**
  - HTML5 Canvas overlay rendering bounding boxes and tracked trajectories over live stream.
  - Polygonal zone drawing interface.
  - Filterable event activity feed with instant MP4 video playback modals.
  - Subsystem diagnostic indicators and real-time inference telemetry graphs.
