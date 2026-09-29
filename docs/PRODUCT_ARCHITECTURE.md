# Smart Spectator Product Architecture — v1.2.0

## System Overview
Smart Spectator is an enterprise-grade, edge-first visual monitoring and event intelligence platform designed specifically for Qualcomm Snapdragon Copilot+ PCs (Windows 11 ARM64) and Android camera nodes over local Wi-Fi.

```
+-----------------------------------------------------------------------------------+
|                            SMART SPECTATOR PLATFORM                               |
+-----------------------------------------------------------------------------------+
|  [Android Camera Node]      [H.264 / TCP]         [Hub Ingestion & Decoder]       |
|  - Camera2 API              ------------>         - Stream Worker                 |
|  - Hardware H.264 Encoder                         - PyAV Hardware / SW Decoder    |
|  - PIN Pairing / TLS                              - Non-blocking Circular Queues  |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                         LOCAL AI PERCEPTION PIPELINE                              |
+-----------------------------------------------------------------------------------+
|  - Frame Sampler (Dynamic Adaptive FPS: 1-15 FPS)                                  |
|  - Spatial Detector: YOLOv8-Nano ONNX (CPU / DirectML / QNN Hexagon NPU)          |
|  - Tracker: ByteTrack with isolated per-camera track contexts                     |
|  - Temporal Feature Extractor: 166-dimensional kinematic trajectory vectors      |
|  - Recurrent Classifier: SpectatorNet BiGRU (FP32 / INT8 Quantized)               |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                        EVENT INTELLIGENCE & AUTOMATION                            |
+-----------------------------------------------------------------------------------+
|  - Polygon Zone Evaluator: Ray casting algorithm (Point-in-Polygon)               |
|  - Compound Rule Engine: Boolean logic, temporal window, active schedule filters  |
|  - Deterministic Prioritizer: CRITICAL | HIGH | MEDIUM | LOW                      |
|  - Causal Timeline Milestone Generator: Exact microsecond timestamp trace         |
|  - Notification Dispatcher: Multi-tier cooldown hierarchy (Global/Camera/Event)   |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                      STORAGE, RECORDING & RETENTION ENGINE                        |
+-----------------------------------------------------------------------------------+
|  - Pre-Roll / Post-Roll Video Buffering                                           |
|  - Fragmented MP4 Packaging (ISO BMFF / AVC1)                                     |
|  - SQLite Database with WAL Journaling & Schema Migration Management              |
|  - Retention Policy Engine: Age & disk pressure eviction with Lock Protection    |
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
|                   EDGE ACCESS LAYER & MONITORING CLIENT (UI)                      |
+-----------------------------------------------------------------------------------+
|  - FastAPI Backend: RESTful endpoints + WebSocket Event Stream (Schema 1.2.0)    |
|  - Vanilla ES6 Monitoring Client: Responsive OLED Dark Theme (#090d16)            |
|  - Forensic Event Inspector with Causal Timeline & Video Player                   |
|  - Interactive Polygon Zone Editor with Vertex Manipulation Handles               |
|  - AI Hardware Diagnostics, Local Model Registry & Offline A/B Evaluator          |
|  - Storage Console, Audit Trail & Zero-Leak Configuration Export/Import           |
+-----------------------------------------------------------------------------------+
```

## Security & Privacy Boundary
1. **Zero External Internet Access**: No cloud metrics, no external telemetry beacons, no external model download URLs.
2. **Path Traversal Protection**: All video clip retrieval operations are sanitized against strict directory boundaries.
3. **Encrypted Authentication & Safe Export**: Session tokens and device credentials are fully scrubbed during configuration backups.
