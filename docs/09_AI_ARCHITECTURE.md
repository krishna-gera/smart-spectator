# Smart Spectator — AI Perception & Event Architecture

**Document ID:** `SS-DOC-009`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Multi-Tier AI Perception Pipeline

Smart Spectator rejects the naive approach of running monolithic vision-language models or heavy end-to-end transformers on raw video frames. Instead, it adopts a **Cascaded Multi-Tier AI Architecture** designed for high throughput, sub-10ms latency on Snapdragon NPUs, and precise temporal reasoning:

```
[ Incoming Decoded Video Stream (30 FPS) ]
                     |
                     v
       [ Motion-Gated Frame Sampler ]
       - Pixel-Differencing / MOG2
       - Bypasses static scenes (saves NPU energy)
       - Samples active streams at 5 FPS
                     |
                     v
   +------------------------------------+
   |   LEVEL 1: SPATIAL OBJECT DETECTOR |
   |   - YOLOv8-Nano / MobileNet-SSD    |
   |   - Accelerated on Hexagon NPU     |
   |   - Latency: ~5.8 ms               |
   +-----------------+------------------+
                     | Detections: { class, bbox, conf }
                     v
   +------------------------------------+
   |   LEVEL 2: MULTI-OBJECT TRACKER    |
   |   - ByteTrack / Kalman Filtering   |
   |   - Bipartite Matching (IoU + App) |
   |   - Generates persistent Track IDs |
   +-----------------+------------------+
                     | Tracklets: { track_id, trajectory, velocity }
                     v
   +------------------------------------+
   |   LEVEL 3: SPECTATORNET EVENT AI   |
   |   - Custom Lightweight Model       |
   |   - Temporal Window Classifier     |
   |   - Detects State Transitions      |
   +-----------------+------------------+
                     | Temporal Events: { event_type, confidence }
                     v
   +------------------------------------+
   |      EVENT & DECISION ENGINE       |
   |   - Rule & ROI Polygon Evaluator   |
   |   - State Machine & Dwell Times    |
   |   - Dispatches Actions & Clips     |
   +------------------------------------+
```

---

## 2. Adaptive Frame Sampling & Motion Gating

Running continuous deep neural network inference on 30 FPS across 4 cameras requires 120 forward passes per second, unnecessarily loading compute silicon on static scenes (e.g., an empty room).

### 2.1 Motion Gating Pre-filter
Before passing a frame to Level 1 Object Detection:
1. Downscale frame to $160 \times 90$ grayscale.
2. Compute absolute difference against previous sampled frame:
   $$\Delta I(x, y) = |I_t(x, y) - I_{t-1}(x, y)|$$
3. If the percentage of pixels exceeding the noise threshold $\tau_{\text{diff}}$ is below $0.5\%$, the scene is classified as **STATIC**:
   - Level 1 deep inference is skipped.
   - Active tracks from Level 2 enter stationary coasting mode.
4. If motion exceeds $0.5\%$, the frame is passed to Level 1.

### 2.2 Decimated Sampling Rate
- Camera stream: $30\text{ FPS}$ (smooth video for viewing and recording).
- Level 1 Inference: $5\text{ FPS}$ ($200\text{ ms}$ interval between evaluations).
- At 5 FPS, track association is mathematically continuous while reducing NPU compute load by $83\%$.

---

## 3. Perception Levels Defined

### 3.1 Level 1: Spatial Object Detector
- **Architecture:** YOLOv8-Nano (or YOLOv9-Compact).
- **Execution Target:** Snapdragon Hexagon NPU via Qualcomm AI Engine Direct (QNN DLC format or ONNX with QNN Execution Provider).
- **Input:** $640 \times 640 \times 3$ RGB, INT8 or FP16 quantized.
- **Output:** Bounding boxes $[x_{\min}, y_{\min}, x_{\max}, y_{\max}]$, confidence scores, and COCO class IDs (person, backpack, bottle, cup, laptop, chair, dog, cat, etc.).

### 3.2 Level 2: Multi-Object Tracker (ByteTrack)
- **Role:** Associates bounding boxes across frames to maintain temporal object identity.
- **Algorithm:** **ByteTrack** using two-stage matching:
  1. High-confidence detections are matched to existing tracks via Hungarian algorithm using IoU (Intersection over Union).
  2. Unmatched tracks are matched against low-confidence detections (recovering occluded or blurred targets).
- **State Estimation:** 8-dimensional Kalman filter vector:
  $$x = [u, v, s, r, \dot{u}, \dot{v}, \dot{s}, \dot{r}]^T$$
  where $(u, v)$ is bbox center, $s$ is scale (area), and $r$ is aspect ratio.
- **Output:** Tracklet objects with persistent `track_id`, total dwell duration, and smoothed trajectory history.

### 3.3 Level 3: SpectatorNet Temporal Event Model
- **Role:** Custom neural network evaluating temporal dynamics across a sliding time window ($T = 3.0\text{ seconds}$).
- **Details:** See `10_MODEL_STRATEGY.md`.
- **Classes:**
  - `OBJECT_PRESENT`
  - `OBJECT_REMOVED`
  - `OBJECT_MOVED`
  - `PERSON_ENTERED`
  - `PERSON_LEFT`
  - `ZONE_INTRUSION`
  - `CAMERA_BLOCKED`
  - `NORMAL_ACTIVITY`

---

## 4. Event Engine & State Machine

The Event Engine receives structured observations containing active detections and tracklets. It evaluates these against the user-configured `MonitoringTask` policies.

### 4.1 State Machine Lifecycle for Monitored Objects

```
                   +-------------------+
                   |   STATE: ABSENT   |
                   +---------+---------+
                             | Target class detected inside ROI
                             v
                   +-------------------+
                   |   STATE: PRESENT  |<----------------+
                   +---------+---------+                 |
                             | Target bbox disappears   | Target reappears
                             v                         | within grace window
                   +-------------------+                 |
                   | STATE: DISENGAGED |-----------------+
                   +---------+---------+
                             | Disengaged duration > T_threshold (e.g. 5 sec)
                             v
           +-----------------------------------+
           |    TRIGGER: OBJECT_REMOVED        |
           | - Dispatch WebSocket Alert        |
           | - Trigger Clip Persistence        |
           +-----------------------------------+
```

### 4.2 Mathematical Trigger Formulations

#### A. Zone Intrusion & Dwell:
Let $P_t = (x_t, y_t)$ be the normalized centroid of a tracked object at time $t$, and $\Omega$ be the user-defined ROI polygon.
$$\text{Inside}(\Omega, P_t) = 1 \iff P_t \in \Omega$$
If $\sum_{\tau = t - T_{\text{dwell}}}^t \text{Inside}(\Omega, P_\tau) \ge T_{\text{dwell}}$, emit `ZONE_INTRUSION_DWELL_EXCEEDED`.

#### B. Camera Obstructed / Blinded:
Compute the mean Laplacian variance of the incoming frame:
$$\sigma^2_{\text{Lap}} = \text{Var}(\nabla^2 I)$$
If $\sigma^2_{\text{Lap}} < \tau_{\text{blur}}$ and mean intensity $\mu_I < 10$ (covered) or $\mu_I > 245$ (glared) continuously for 3.0 seconds, emit `CAMERA_BLOCKED`.

---

## 5. Phase 2 Implementation Realization

Phase 2 realizes Level 1 Spatial Object Detection and Level 2 Multi-Object Tracking as decoupled services:
- **`services/ai_engine/frame_sampler.py`**: Monotonic 5 FPS decimation with $160 \times 90$ pixel delta motion gating.
- **`services/ai_engine/detector.py`**: `YOLOObjectDetector` executing ONNX runtime graphs with letterbox preprocessing and $[0.0, 1.0]$ normalized bounding box conversions.
- **`services/ai_engine/tracker.py`**: `ByteTrackTracker` implementing two-stage bipartite matching via `scipy.optimize.linear_sum_assignment`, preserving persistent track IDs, centroid trajectories, and normalized velocity vectors across occlusions.
- **`services/ai_engine/observation_builder.py`**: Synthesizes detections, tracklets, and telemetry into the `Observation` schema (`shared/schemas/v1/models.py`).
- **`services/ai_engine/pipeline.py`**: Non-blocking `AIPipeline` with bounded queue (`Queue(maxsize=2)`) and multi-camera context isolation.

