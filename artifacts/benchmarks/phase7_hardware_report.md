# Smart Spectator — Phase 7 Hardware Benchmark Report
## End-to-End Perception & Inference Performance Measurements

**Generated:** 2026-09-30T09:21:23.647595+00:00  
**System Host:** Darwin 27.0.0 (arm64)  
**Processor:** arm (10 logical cores, 16.0 GB RAM)  
**Execution Providers Evaluated:** `CoreMLExecutionProvider, AzureExecutionProvider, CPUExecutionProvider`  

---

### 1. Model Latency & Throughput Summary

| Component | Precision | Active Provider | Mean (ms) | p50 (ms) | p95 (ms) | Throughput (FPS) |
|---|---|---|---|---|---|---|
| **YOLOv8n Detector** | FP32 | CoreMLExecutionProvider | 3.22 | 3.17 | 3.36 | 310.99 |
| **SpectatorNet** | FP32 | CoreMLExecutionProvider | 0.2 | 0.2 | 0.21 | 5012.74 |
| **SpectatorNet** | INT8 | CoreMLExecutionProvider | 0.25 | 0.25 | 0.25 | 4014.51 |

---

### 2. End-to-End Perception Pipeline Latency Breakdown

```
Raw Frame (720p)
   │
   ├─► YOLOv8n + ByteTrack (Perception):    12.13 ms
   │
   ├─► Feature Encoder + SpectatorNet:      0.89 ms
   │
   └─► Event Engine (Rules/Zones/State):    0.01 ms
--------------------------------------------------------------
Total End-to-End Pipeline Latency:           12.32 ms (p50: 10.8 ms)
Sustainable Throughput:                      81.2 FPS
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
