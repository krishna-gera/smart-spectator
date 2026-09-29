# Smart Spectator — Architecture Decision Records (ADR Log)

**Document ID:** `SS-DOC-016`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## ADR-001: Why Local-First Architecture?
- **Context:** Visual monitoring requires processing continuous high-bandwidth video streams containing sensitive private home or office environments.
- **Decision:** Architect the entire system to run strictly within the local area network (LAN) without requiring cloud servers, accounts, or WAN routing.
- **Reason:** Guarantees absolute user privacy, zero cloud operational subscription costs, zero external bandwidth bottlenecks, and sub-100ms deterministic response latency.
- **Alternatives Considered:** Cloud-hosted video processing (AWS Kinesis / GCP Vertex AI), Hybrid cloud relay.
- **Consequences:** The Desktop Hub must bear full responsibility for compute, storage, and device management; remote access outside LAN requires a user-configured VPN (e.g. Tailscale / WireGuard) in future phases.

---

## ADR-002: Why Desktop Hub on Snapdragon PC?
- **Context:** Edge smartphones lack the continuous thermal dissipation, sustained battery endurance, and unified compute capacity to run multi-camera AI perception 24/7.
- **Decision:** Position the Snapdragon-powered PC as the central Desktop Hub, executing all video decoding, temporal AI perception, event evaluation, and storage.
- **Reason:** Leverages the 45+ TOPS Hexagon NPU on Snapdragon X-series platforms to achieve desktop-class AI throughput at ultra-low power envelopes ($< 1.5\text{W}$ NPU load), leaving smartphones lightweight and thermally cool.
- **Alternatives Considered:** Processing directly on smartphones, dedicated Linux server / Raspberry Pi.
- **Consequences:** The Snapdragon PC must remain awake during active monitoring periods (handled via standard OS wake lock APIs).

---

## ADR-003: Why Flutter for Presentation Layers?
- **Context:** The project requires an Android camera application, a Desktop Hub interface (Windows/macOS), and a responsive client dashboard.
- **Decision:** Select Flutter as the primary UI framework for the Android node and Desktop Hub, with Flutter Web / React for the browser client.
- **Reason:** Delivers native compilation on Windows, macOS, and Android from a single shared Dart codebase; high-performance GPU-accelerated Skia/Impeller rendering pipeline.
- **Alternatives Considered:** React Native (inferior desktop support), Electron (excessive memory footprint), Native Kotlin + Swift (quadruples UI development overhead).
- **Consequences:** Low-level native camera capture on Android requires a lightweight Kotlin/NDK platform channel for optimal `MediaCodec` control.

---

## ADR-004: Why Python / FastAPI for Local Backend Services?
- **Context:** The local backend must orchestrate asynchronous network I/O, expose REST/WebSocket APIs, interface with computer vision libraries, and manage AI runtimes.
- **Decision:** Use Python 3.11+ with FastAPI, Uvicorn, and PyAV / FFmpeg for the Hub backend core.
- **Reason:** FastAPI provides native asynchronous concurrency (`asyncio`), automated OpenAPI documentation, high developer velocity, and direct, native integration with PyTorch, ONNX Runtime, and Qualcomm AI Hub Python SDKs.
- **Alternatives Considered:** Go (inferior AI/ML runtime ecosystem), C++ (excessive boilerplate and slower iteration speed), Node.js (poor tensor manipulation performance).
- **Consequences:** CPU-bound video decoding and frame buffering must be offloaded to native background threads or C-extensions (PyAV/NumPy) to prevent Python Global Interpreter Lock (GIL) contention.

---

## ADR-005: Why SQLite with WAL Mode?
- **Context:** The Hub requires structured persistence for paired devices, camera states, event logs, monitoring tasks, and clip references.
- **Decision:** Embed SQLite 3 configured with Write-Ahead Logging (`PRAGMA journal_mode = WAL`).
- **Reason:** Zero configuration, zero external process dependencies, atomic transactions, microsecond read latencies, and flawless concurrency for single-writer / multi-reader desktop access.
- **Alternatives Considered:** PostgreSQL (requires separate server service and installation friction), MongoDB, Flat JSON files (lacks ACID guarantees and indexing).
- **Consequences:** Database writes must funnel through an asynchronous write queue to ensure sequential durability without locking read threads.

---

## ADR-006: Why CameraSource Abstraction?
- **Context:** While Phase 1 focuses on Android smartphone nodes, the production system must support legacy security cameras, RTSP streams, ONVIF PTZs, and USB webcams.
- **Decision:** Establish an abstract `CameraSource` interface defining standardized connection, streaming, frame polling, and status methods.
- **Reason:** Fully decouples video ingestion from the downstream AI perception pipeline, ring buffers, and event engine. Future camera protocols can be added with zero changes to AI or UI layers.
- **Alternatives Considered:** Hardcoding Android-specific streaming protocols directly into the AI pipeline.
- **Consequences:** Stream engine must maintain a normalization layer converting diverse input streams into standard BGR/RGB frame arrays.

---

## ADR-007: Why Cascaded Multi-Tier AI Architecture?
- **Context:** Visual intelligence involves detection, tracking, and complex event comprehension. Running monolithic multi-modal models continuously is too slow and power-hungry.
- **Decision:** Decompose AI perception into three distinct tiers: Level 1 (Object Detection), Level 2 (Multi-Object Tracking), and Level 3 (Custom Temporal Event Classification).
- **Reason:** Maximizes computational efficiency. Level 1 runs at decimated rates (5 FPS); Level 2 runs lightweight Kalman tracking at negligible CPU cost; Level 3 evaluates temporal feature windows only when target objects are active.
- **Alternatives Considered:** Monolithic Vision-Language Model (VLM), End-to-end Video Action Transformer.
- **Consequences:** Requires maintaining state tracking between detection and temporal event classification.

---

## ADR-008: Why Custom Temporal Event Model (SpectatorNet)?
- **Context:** Standard object detection models only identify what an object is in a static snapshot, failing to discern whether an object has been removed, displaced, or tampered with over time.
- **Decision:** Develop and train a custom lightweight temporal neural network (**SpectatorNet**) combining a vision backbone (MobileNetV3) with a temporal recurrent sequence encoder (BiGRU).
- **Reason:** Provides the core proprietary AI innovation for the competition; achieves temporal event reasoning at $< 5\text{M}$ parameters and sub-10ms latency on Snapdragon NPU.
- **Alternatives Considered:** Relying strictly on rule-based heuristics (too brittle under lighting shifts/occlusions), using cloud VLMs (violates local-first privacy and latency goals).
- **Consequences:** Requires creating the curated Smart Spectator Dataset for training and validation.

---

## ADR-009: Why Event-Based Recording with Circular Ring Buffer?
- **Context:** Continuous 24/7 video recording across multiple cameras rapidly consumes local SSD storage (e.g. 50GB/day per camera) and degrades consumer drive write endurance.
- **Decision:** Implement an in-memory/scratch disk circular ring buffer maintaining the most recent 15 seconds of rolling video. When an event is triggered, the Hub writes $T - 15\text{s}$ through $T + 15\text{s}$ into a permanent MP4 clip.
- **Reason:** Saves over $95\%$ of disk storage while guaranteeing that critical context leading up to an event is permanently captured.
- **Alternatives Considered:** 24/7 continuous recording, recording only starting *after* event trigger (misses critical root cause).
- **Consequences:** Hub RAM or scratch cache must allocate approximately $15\text{MB}$ per active camera stream to buffer rolling frames.

---

## ADR-010: Why Snapdragon-First Inference Abstraction?
- **Context:** The system must run optimally on Snapdragon-powered Windows PCs utilizing Qualcomm Hexagon NPUs, while remaining developable and testable on macOS and standard x86 laptops.
- **Decision:** Implement the `InferenceProvider` interface with automatic hardware selection prioritizing Qualcomm QNN (Hexagon NPU), falling back to DirectML / CoreML (GPU), and CPU.
- **Reason:** Maximizes competition demonstration impact on Snapdragon hardware without blocking cross-platform team development.
- **Alternatives Considered:** Writing code strictly locked to Qualcomm QNN APIs (breaks macOS local development), using CPU-only inference (fails competition performance potential).
- **Consequences:** The build pipeline must package ONNX Runtime with execution provider fallbacks.

---

## ADR-011: Why H.264 over TCP/WebSocket for Ingest?
- **Context:** Android phones must stream video to the Hub with minimal latency and maximal reliability over Wi-Fi.
- **Decision:** Use hardware-encoded H.264 Annex-B NAL units framed with a custom 24-byte binary header over a dedicated TCP/WebSocket socket.
- **Reason:** Universal Android `MediaCodec` hardware support, zero licensing issues, sub-50ms glass-to-glass LAN latency, and guaranteed packet delivery without UDP packet dropping on congested Wi-Fi.
- **Alternatives Considered:** WebRTC (higher complexity, signaling overhead), RTSP server on phone (excessive battery consumption and native library friction on Android).
- **Consequences:** TCP flow control handles backpressure; severe network congestion requires dynamic frame dropping at the application layer.

---

## ADR-012: Why ByteTrack for Level 2 Tracking?
- **Context:** Multi-object tracking must associate bounding boxes across frames with extreme computational efficiency.
- **Decision:** Select **ByteTrack** for Level 2 temporal association.
- **Reason:** Operates in $< 2\text{ms}$ on CPU, does not require a heavy deep re-identification (Re-ID) neural network, and recovers occluded objects by matching low-confidence detection boxes.
- **Alternatives Considered:** DeepSORT (requires heavy second-stage feature extraction), BoT-SORT (higher computational overhead).
- **Consequences:** If an object is occluded for extended periods ($> 30\text{ seconds}$), track ID may switch unless spatial proximity heuristics are applied.
