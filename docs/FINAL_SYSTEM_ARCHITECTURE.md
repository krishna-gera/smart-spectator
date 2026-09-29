# Smart Spectator Final System Architecture

## 1. System Vision & Architecture Topology

Smart Spectator is a 100% local-first, low-latency visual intelligence platform designed for edge edge computing devices (Qualcomm Snapdragon, Apple Silicon, x86_64 Linux). It transforms standard commodity Android mobile phones into intelligent smart cameras, performing temporal activity understanding and spatial rule evaluation in real time without cloud dependencies.

```mermaid
graph TD
    subgraph Edge Camera Device
        AC[Android Camera2 HAL] --> MF[Media Transport / WebSocket]
        CC[Control Client / Telemetry] --> WS_CAM[WebSocket /camera/stream]
    end

    subgraph Hub Host (Edge Gateway)
        subgraph Ingestion & Protocol
            WS_CAM --> SIS[Stream Ingest Session / Bounded Ring Buffer]
            SIS --> MG[Motion Gating Engine]
        end

        subgraph Visual Perception Pipeline
            MG -->|Motion Detected| YOLO[YOLOv8n ONNX Detector]
            MG -->|Static Scene| SKIP[Bypass Deep Perception]
            YOLO --> BT[ByteTrack Multi-Object Tracker]
            BT --> OBS[Structured Observation Window (30 frames)]
            OBS --> TF[Temporal Feature Extraction (166-dim)]
            TF --> SN[SpectatorNet GRU Sequence Classifier]
        end

        subgraph Event Engine & Storage
            SN --> RE[Spatial & Temporal Rule Engine]
            RE --> CR[Clip Recorder / Pre-Write Disk Guard]
            RE --> DB[(SQLite Database / WAL Mode)]
            CR --> MP4[Rolling MP4 Storage]
        end

        subgraph Monitoring & Control
            DB --> API[FastAPI REST & Diagnostic Health API]
            RE --> WS_CLIENT[WebSocket Broadcast Hub /ws/events]
        end
    end

    subgraph Monitoring Client
        WS_CLIENT --> UI[Vanilla Web Client (Grid, Timeline, Rules, Zones)]
        API --> UI
    end
```

---

## 2. Component Subsystems

### 2.1 Ingestion & Transport
- **Protocol**: Binary WebSocket sending encoded JPEG frames with framing headers (timestamp, sequence number, device ID).
- **Control & Auth**: JSON control channel over WebSockets / HTTP REST. Device pairing authenticated via 6-digit expiring PINs and opaque tokens.
- **Buffer Management**: Strict FIFO ring buffer (`collections.deque(maxlen=90)`) discarding oldest unconsumed frames under backpressure.

### 2.2 AI Perception Pipeline
- **Motion Gating**: Frame-to-frame difference thresholding skipping up to 83% of redundant inference passes.
- **Detector**: YOLOv8n ONNX runtime session optimized for Snapdragon NPU (QNN), DirectML, CoreML, and CPU.
- **Tracker**: ByteTrack maintaining persistent track IDs across occlusions and motion jitter.
- **Temporal Classifier (SpectatorNet)**: 2-layer GRU accepting 30-frame temporal feature windows (166 dimensions: motion dynamics, spatial velocity, acceleration, zone occupancy, object interactions) to classify complex multi-frame human activities.

### 2.3 Rule Engine & Zone System
- **Polygon Geometry**: Point-in-polygon ray-casting evaluating object bounding box centers and footprints against user-defined zones.
- **Temporal Rules**: Evaluates conditions such as `ZONE_LOITERING` (duration > threshold), `OBJECT_REMOVED` (interaction disappearance), and `PERSON_ENTERED`.
- **Pre-Write Disk Guard**: Automatically halts video disk writing when host free space is under 500 MB to safeguard host stability while retaining structured event metadata.

### 2.4 Monitoring Frontend
- Zero-dependency, lightweight modern web dashboard built with HTML5, CSS Grid/Flexbox, and ES6 JavaScript.
- Dynamic polygon canvas for drawing detection zones.
- Real-time event notifications via WebSockets with instant replay of recorded MP4 video clips.
