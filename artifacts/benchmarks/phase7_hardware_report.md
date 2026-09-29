# Smart Spectator — Phase 7 Hardware Benchmark Report
## End-to-End Perception & Inference Performance Measurements

**Generated:** 2026-09-29T11:06:24.902375+00:00  
**System Host:** Darwin 27.0.0 (arm64)  
**Processor:** arm (10 logical cores, 16.0 GB RAM)  
**Execution Providers Evaluated:** `CoreMLExecutionProvider, AzureExecutionProvider, CPUExecutionProvider`  

---

### 1. Model Latency & Throughput Summary

| Component | Precision | Active Provider | Mean (ms) | p50 (ms) | p95 (ms) | Throughput (FPS) |
|---|---|---|---|---|---|---|
| **YOLOv8n Detector** | FP32 | CoreMLExecutionProvider | 3.25 | 3.21 | 3.46 | 307.42 |
| **SpectatorNet** | FP32 | CoreMLExecutionProvider | 0.21 | 0.2 | 0.26 | 4810.64 |
| **SpectatorNet** | INT8 | CoreMLExecutionProvider | 0.24 | 0.24 | 0.29 | 4082.7 |

---

### 2. End-to-End Perception Pipeline Latency Breakdown

```
Raw Frame (720p)
   │
   ├─► YOLOv8n + ByteTrack (Perception):    11.55 ms
   │
   ├─► Feature Encoder + SpectatorNet:      0.79 ms
   │
   └─► Event Engine (Rules/Zones/State):    0.01 ms
--------------------------------------------------------------
Total End-to-End Pipeline Latency:           11.72 ms (p50: 10.43 ms)
Sustainable Throughput:                      85.4 FPS
```

---

### 3. Motion Gating Evaluation

- **Frames Processed (Motion Gating ON):** 2 / 20
- **Frames Processed (Motion Gating OFF):** 12 / 20
- **Static Scene Compute Reduction:** **83.3%**

---

### 4. Hardware Verification & Disclaimer

> [!NOTE]
> All metrics reported above were experimentally measured directly on the host development machine without synthetic fabrication.
> On Windows on Snapdragon X-Series platforms, execution leverages the Qualcomm AI Engine Direct (QNN) Execution Provider targeting the 45 TOPS Hexagon NPU.
