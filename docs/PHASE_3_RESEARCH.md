# Smart Spectator — Phase 3 Research & Experiment Log

**Document ID:** `SS-DOC-022`  
**Phase:** Phase 3 (Research & Investigation)  
**Status:** Approved  

---

## 1. Dataset Landscape & Public Alignment

| Dataset | License | Focus | Evaluation for Smart Spectator |
|---|---|---|---|
| **Something-Something v2** | Non-commercial / Academic | Fine-grained object interactions ("dropping X", "taking X away") | Provided high-level taxonomy inspiration for `OBJECT_REMOVED` and `OBJECT_MOVED`. However, labels are video-level rather than structured bounding-box trajectory sequences. |
| **UCF101 / Kinetics-400** | Non-commercial research | Coarse human actions (sports, instruments) | Too coarse for localized security and desktop event detection; human action recognition is distinct from physical state transitions. |
| **ShanghaiTech Campus** | Academic | Static camera surveillance anomalies | Useful for anomaly detection baselines, but frames are fixed 1080p CCTV without mobile phone camera dynamics. |

**Strategic Decision:** To achieve high fidelity on repurposed mobile nodes, Smart Spectator implements a dedicated feature-encoding pipeline that transforms Level 1/2 tracking outputs directly into structured temporal representations, rather than relying on heavy end-to-end video pixel transformers.

---

## 2. Architecture Trade-offs & Rejected Approaches

### 2.1 3D Convolutional Networks (C3D / I3D / SlowFast)
- **Evaluation:** Operates directly on raw RGB pixel volumes ($[B, 3, T, H, W]$).
- **Why Rejected:** Prohibitively large parameter size ($> 30\text{M}$ params), $> 300\text{ MB}$ memory footprint, $> 80\text{ ms}$ inference latency. Cannot run concurrently on Snapdragon NPU alongside 4 active video decoders and YOLO detectors.

### 2.2 Temporal Transformer (ViT / TimeSformer on structured features)
- **Evaluation:** Evaluated self-attention across 30 timesteps.
- **Finding:** Across a 30-timestep sequence, self-attention adds $O(T^2)$ computational overhead without improving accuracy over a 2-layer Bidirectional GRU with Temporal Attention Pooling. The GRU converges faster, requires only 152k parameters (0.59 MB), and compiles natively to Qualcomm Hexagon Tensor Processor (HTP) execution graphs.

---

## 3. Snapdragon Deployment Research (QNN / Hexagon NPU)

### 3.1 Operator Compatibility for Qualcomm AI Engine Direct (QNN)
- Qualcomm QNN SDK v2.20+ provides full support for:
  - `MatMul`, `Gemm`
  - `LayerNorm` (accelerated on Hexagon DSP)
  - `GRU` / `LSTM` unrolled recurrent operations
  - `Softmax`
  - `Relu`
- All operators in `SpectatorNet` were selected specifically from the set of verified Qualcomm HTP-supported ops.
- The exported ONNX graph (`ai/models/spectatornet.onnx`) uses Opset 17 with standard operations that compile directly via `qai-hub compile --target-runtime qnn_lib_aarch64_windows`.

### 3.2 Dynamic Quantization Findings
- Dynamic INT8 quantization (`spectatornet_int8.onnx`) reduces model footprint from **0.59 MB to 0.52 MB**.
- On CPU, inference latency is **0.161 ms** (FP32) vs **0.170 ms** (INT8). On standard desktop CPU, FP32 and INT8 latencies are both sub-millisecond due to the minimal parameter count (152k). On the target Snapdragon Hexagon NPU, INT8 execution leverages dedicated vector/tensor instructions for maximum energy efficiency ($< 0.5\text{W}$).
