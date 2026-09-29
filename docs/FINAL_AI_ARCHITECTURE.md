# Smart Spectator — Three-Level Hierarchical AI Architecture & Inference Engine

**Document ID:** SS-DOC-029  
**Version:** 1.1.0  
**Phase:** 8 (Real-Device Deployment, End-to-End Validation & Demo Readiness)  
**Status:** Certified Specification & Hardware Validation Report  

---

## 1. Architectural Philosophy

Traditional edge visual surveillance architectures suffer from two main flaws:
1. **Raw frame flooding:** Streaming unprocessed video frames to centralized cloud servers compromises privacy, introduces variable internet latency, and incurs heavy bandwidth costs.
2. **Naive frame-by-frame classification:** Evaluating heavy multi-modal video transformers directly on every camera frame exceeds the thermal and battery envelope of edge edge devices.

Smart Spectator resolves these challenges through a **three-level decoupled perception hierarchy**:
- **Level 1 (Spatial Perception):** Extracts instantaneous bounding boxes and semantic class labels from individual video frames.
- **Level 2 (Spatiotemporal Association):** Maintains persistent object identities and motion trajectories across frames, surviving occlusions and missed detections.
- **Level 3 (Temporal Intelligence):** Evaluates behavioral dynamics across sliding time windows using a lightweight recurrent neural network (SpectatorNet).

---

## 2. Level 1: Spatial Object Detection (YOLOv8n)

- **Architecture:** Ultralytics YOLOv8-Nano (anchor-free single-stage detector).
- **Format:** Open Neural Network Exchange (ONNX) format (`detector_v1.onnx`).
- **Input Dimension:** Tensor `(1, 3, 640, 640)` in float32 format, normalized `[0.0, 1.0]`, letterbox padded.
- **Output Dimension:** Tensor `(1, 84, 8400)` representing 4 bounding box coordinates and 80 COCO semantic class scores across 8,400 candidate anchors.
- **Post-Processing:**
  - Non-Maximum Suppression (NMS) with Intersection-over-Union (IoU) threshold `0.45` and confidence cutoff `0.35`.
  - Normalized coordinate projection `[x1, y1, x2, y2] \in [0.0, 1.0]^4`.
- **Target Accelerators:** Qualcomm Hexagon NPU via QNN Execution Provider, DirectML (Windows GPU), Apple Neural Engine (CoreML), or CPU.

---

## 3. Level 2: Multi-Object Tracking (ByteTrack)

- **Algorithm:** ByteTrack with two-tier association.
- **State Estimation:** 8-dimensional Kalman filter state vector:
  $$\mathbf{x} = [x_c, y_c, a, h, \dot{x}_c, \dot{y}_c, \dot{a}, \dot{h}]^T$$
  where $(x_c, y_c)$ is bounding box center, $a$ is aspect ratio, $h$ is box height, and dotted variables are temporal velocities.
- **Data Association:**
  - **Tier 1:** High-confidence detections ($conf \ge 0.50$) associated with existing tracks using Hungarian algorithm on IoU distance matrix.
  - **Tier 2:** Unmatched tracks matched against lower-confidence detections ($0.10 \le conf < 0.50$) to recover tracks through partial occlusion or motion blur.
- **Lifecycle Management:**
  - Track states: `Tentative -> Active -> Lost -> Deleted`.
  - Re-identification grace period: 30 consecutive frames.
- **Node Isolation:** Completely isolated tracker state instances per physical camera stream, preventing tracklet crosstalk across multiple paired phones.

---

## 4. Level 3: Temporal Intelligence (SpectatorNet GRU)

- **Architecture:** Compact recurrent neural network designed specifically for edge NPU execution.
- **Input Feature Vector:** 64-dimensional feature representation per time step:
  - Global scene statistics: total active tracks, person count, vehicle count, animal count, package count.
  - Motion dynamics: aggregated velocity magnitude, acceleration, spatial centroid spread.
  - Spatial proximity features: relative distances to defined monitor zones.
- **Temporal Window:** Sliding window of 16 consecutive frames (3.2 seconds of history at 5 FPS sampling rate).
- **Input Tensor Shape:** `(1, 16, 64)` float32 or INT8.
- **Network Layers:**
  1. Dense projection layer: $64 \to 64$ with ReLU activation.
  2. 2-layer Gated Recurrent Unit (GRU): hidden dimension = 64, bidirectional = False.
  3. Attention pooling head across temporal sequence.
  4. Classification MLP head: $64 \to 32 \to 6$ with Softmax activation.
- **Output Classes (6 Target Behaviors):**
  1. `NORMAL_ACTIVITY`
  2. `PERSON_ENTERED`
  3. `LOITERING`
  4. `OBJECT_LEFT`
  5. `RAPID_MOTION`
  6. `CAMERA_BLOCKED`

---

## 5. Inference Manager & Execution Provider Fallback Chain

Smart Spectator implements an adaptive execution provider manager (`ai.inference.manager.ProviderManager`) that dynamically inspects host silicon and binds the optimal hardware execution engine:

```
+-------------------------------------------------------------+
|               Host Silicon Inspection (Startup)             |
+-------------------------------------------------------------+
                               |
                               v
                     Is Hexagon NPU Present?
                      (QNNExecutionProvider)
                               |
            +------------------+------------------+
            | Yes                                 | No
            v                                     v
+------------------------+             Is DirectML Present?
| Hexagon NPU (Qualcomm) |            (DmlExecutionProvider)
+------------------------+                        |
                                    +-------------+-------------+
                                    | Yes                       | No
                                    v                           v
                         +--------------------+       Is CoreML Present?
                         | DirectML GPU (Win) |      (Apple Silicon ANE)
                         +--------------------+                 |
                                                  +-------------+-------------+
                                                  | Yes                       | No
                                                  v                           v
                                       +-------------------+       Is CUDA Present?
                                       | CoreML / ANE (Mac)|      (NVIDIA GPU)
                                       +-------------------+            |
                                                              +---------+---------+
                                                              | Yes               | No
                                                              v                   v
                                                   +---------------+     +---------------+
                                                   | NVIDIA CUDA   |     | CPU Fallback  |
                                                   +---------------+     +---------------+
```

---

## 6. Model Quantization & Snapdragon NPU Acceleration

To maximize TOPS/Watt efficiency on Snapdragon X Elite and Snapdragon 8-series platforms, SpectatorNet was quantized from FP32 to **INT8 precision** using post-training quantization (PTQ):
- **Weights & Activations:** Quantized to signed 8-bit integers (`int8`).
- **Calibration Dataset:** Representative temporal feature vectors derived from multi-camera motion logs.
- **Accuracy Retention:** >99.2% classification agreement with baseline FP32 model.
- **Model Footprint:** Reduced by 12.2% (from 615 KB down to 540 KB).
- **Execution Latency:** Measured at **0.25 ms** on Apple Silicon (host benchmark) and expected sub-**0.20 ms** on Qualcomm Hexagon NPU.

---

## 7. Model Integrity & Cryptographic Verification

All production model weights are cryptographically verified against `ai/models/releases/manifest.json` before loading into memory (`ai.models.validator.ModelValidator`):

| Model Artifact | File Name | Precision | Expected SHA-256 | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **YOLOv8n Detector** | `detector_v1.onnx` | FP32 | `05c0c73bb9bb9080447b1e986da7f40fbbed530280f472d0e3894263cc0565bd` | `VERIFIED PASS` |
| **SpectatorNet FP32** | `spectatornet_v1.onnx` | FP32 | `846724fd28fa2b344a88e90557177a22c51951634190d55855f666bb20b9ffc6` | `VERIFIED PASS` |
| **SpectatorNet INT8** | `spectatornet_v1_int8.onnx` | INT8 | `475585930c14a02b4b3374d37f9312a317c75dc7d1f6d6e29b9dbf2aeacc62a3` | `VERIFIED PASS` |

- **Tamper Protection:** Any unauthorized modification to ONNX weight files causes `ModelIntegrityError` at startup, blocking corrupted execution.
- **Automated Validation:** Verified during startup sequence and exposed via `GET /api/v1/system/diagnostics` (Subsystem: `models`).

---

## 8. Real Hardware Performance Profile

The following benchmarks were generated using `scripts/validate_snapdragon_runtime.py` executing 100 warm iterations per model.

| Metric | SpectatorNet (FP32) | SpectatorNet (INT8) | YOLOv8n (FP32) |
| :--- | :--- | :--- | :--- |
| **Host Environment** | macOS ARM64 (Apple Silicon) | macOS ARM64 (Apple Silicon) | macOS ARM64 (Apple Silicon) |
| **Execution Provider** | `CoreMLExecutionProvider` | `CoreMLExecutionProvider` | `CoreMLExecutionProvider` |
| **Mean Latency** | `0.22 ms` | `0.26 ms` | `3.48 ms` |
| **P50 Latency** | `0.21 ms` | `0.25 ms` | `3.38 ms` |
| **P95 Latency** | `0.27 ms` | `0.29 ms` | `3.87 ms` |
| **Throughput (Inference FPS)** | `4,501.2 FPS` | `3,910.4 FPS` | `286.9 FPS` |
| **Snapdragon X Elite Target (Expected)** | `< 0.20 ms` (Hexagon NPU) | `< 0.15 ms` (Hexagon NPU) | `1.8 - 2.5 ms` (Hexagon NPU / DML) |
| **Verification Tag** | `MEASURED` (Host CoreML) | `MEASURED` (Host CoreML) | `MEASURED` (Host CoreML) |
