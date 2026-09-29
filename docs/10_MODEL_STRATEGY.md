# Smart Spectator — Custom AI Model Strategy (SpectatorNet)

**Document ID:** `SS-DOC-010`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  
**Internal Model Codename:** `SpectatorNet-v1`  

---

## 1. Motivation: Beyond Static Spatial Bounding Boxes

Standard computer vision surveillance relies almost exclusively on static object detection (e.g. YOLO, Faster-RCNN). While detection identifies that a "bottle" or "person" exists in a single isolated frame, it is fundamentally blind to **temporal dynamics, causal state transitions, and context over time**:
- Did someone pick up the mug and walk away, or did the camera just suffer a momentary detection flicker?
- Was an object removed, or was it momentarily occluded by someone walking in front of it?
- Is a person loitering, completing a task, or falling?

Conversely, massive 7B+ parameter Vision-Language Models (VLMs) like LLaVA or GPT-4V are computationally prohibitive for real-time edge processing on consumer laptops, requiring tens of gigabytes of RAM and yielding latencies exceeding 2000ms per frame.

**SpectatorNet** bridges this gap: a purpose-engineered, lightweight ($< 5\text{M}$ parameters, $< 20\text{MB}$ memory footprint) temporal neural network designed specifically to run at sub-10ms latency on the Snapdragon Hexagon NPU.

---

## 2. SpectatorNet Architecture Specification

```
                          INPUT STREAM: Sliding Window of T=16 Frames
                             (Sampled at 5 FPS over 3.2 seconds)
                                              |
                                              v
             +-----------------------------------------------------------------+
             |        STAGE 1: SPATIAL FEATURE BACKBONE (Weight-Shared)        |
             |        - MobileNetV3-Small (or EfficientNet-Lite0)              |
             |        - Input: [16, 3, 224, 224]                               |
             |        - Output: [16, 576] Spatial Feature Embeddings           |
             +--------------------------------+--------------------------------+
                                              |
                                              | Concat with Level 1/2 metadata:
                                              | Normalized Bounding Box Sequences
                                              | & Class Distribution Vectors [16, 16]
                                              v
             +-----------------------------------------------------------------+
             |              STAGE 2: TEMPORAL SEQUENCE ENCODER                 |
             |        - 2-Layer Bidirectional GRU (Hidden Dim: 256)            |
             |          (OR Lightweight 3-Layer Temporal Transformer)          |
             |        - Captures velocity, acceleration, appearance delta      |
             |        - Output: [1, 512] Temporal Context Vector               |
             +--------------------------------+--------------------------------+
                                              |
                                              v
             +-----------------------------------------------------------------+
             |           STAGE 3: CLASSIFICATION & CONFIDENCE HEAD             |
             |        - Linear(512, 128) -> ReLU -> Dropout(0.2)               |
             |        - Linear(128, Num_Classes) -> Softmax                    |
             +--------------------------------+--------------------------------+
                                              |
                                              v
               OUTPUT: Multiclass Probability Distribution over Event Classes
```

---

## 3. Model Target Classes

| Class Code | Class Name | Operational Description |
| :--- | :--- | :--- |
| `EVT_00` | `NORMAL_BACKGROUND` | Static scene, benign background noise (curtains moving, light shift). |
| `EVT_01` | `OBJECT_REMOVED` | Target object present in ROI, interacted with, and removed from frame. |
| `EVT_02` | `OBJECT_MOVED` | Target object displaced from baseline coordinates but remains in scene. |
| `EVT_03` | `PERSON_ENTERED` | Person crosses into monitored scene boundary. |
| `EVT_04` | `PERSON_LEFT` | Person departs monitored scene boundary. |
| `EVT_05` | `ZONE_LOITERING` | Person or vehicle dwells in restricted zone beyond dwell threshold. |
| `EVT_06` | `CAMERA_BLOCKED` | Lens obscured by physical obstruction, hand, or spray. |
| `EVT_07` | `TASK_COMPLETED` | Sequence of target interactions completed (e.g. appliance cycle finished). |

---

## 4. Hardware Optimization & Export Pipeline

To achieve maximal acceleration on the Snapdragon Hexagon NPU, SpectatorNet follows a strict compilation and quantization lifecycle:

```
[ PyTorch Checkpoint (.pt) ]
             |
             v (torch.onnx.export with dynamic/fixed batching, Opset 17)
[ Standard ONNX Model (.onnx) ]
             |
             v (ONNX Simplifier & Operator Verification)
[ Clean ONNX Graph ]
             |
             +------------------------------------------+
             |                                          |
             v (Qualcomm AI Hub CLI / Workbench)        v (DirectML / CoreML fallback)
  [ qai-hub compile & profile ]               [ ONNX Runtime FP16 ]
  - Target: Snapdragon X Elite (Hexagon NPU)   - DirectML / CoreML Provider
  - INT8 / FP16 Quantization Calibration
             |
             v
  [ QNN DLC Model (.dlc) ]
  (Direct Hexagon NPU native binary)
```

### 4.1 Quantization Strategy
- **Calibration Dataset:** 500 representative multi-frame sequences spanning daytime, night, indoor, and outdoor scenes.
- **Quantization Mode:** Post-Training Quantization (PTQ) to INT8 (weights and activations) with Per-Channel Quantization on convolutional layers.
- **Accuracy Degradation Threshold:** Quantized INT8 model must retain $\ge 98.5\%$ of FP32 baseline Top-1 validation accuracy.

---

## 5. Performance Targets on Snapdragon X-Series

| Metric | Target Specification |
| :--- | :--- |
| **Model Size on Disk** | $\le 12\text{ MB}$ (INT8 quantized) |
| **Active RAM Footprint** | $\le 25\text{ MB}$ |
| **Inference Latency (Hexagon NPU)** | $\le 7.5\text{ ms}$ per temporal window |
| **Throughput (Hexagon NPU)** | $\ge 120\text{ inferences / sec}$ |
| **Power Consumption** | $< 0.8\text{ W}$ incremental NPU power |
