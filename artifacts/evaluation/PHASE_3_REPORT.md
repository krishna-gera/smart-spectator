# Smart Spectator — Phase 3 Model Evaluation & Research Report

**Report ID:** `PHASE-3-EVAL-001`  
**Execution Date:** 2026-09-29  
**Model Name:** `SpectatorNet-GRU`  
**Evaluation Scope:** Custom Dataset, Temporal Event Modeling, Ablation & Benchmark Suite  

---

## 1. Dataset Overview
- **Dataset Version:** `v1.0-synthetic`
- **Total Samples:** 180 sequence samples (5,400 observation frames total)
- **Sequence Length:** 30 timesteps per sample (approx. 6.0 seconds at 5.0 FPS)
- **Number of Classes:** 9 event classes
- **Class Distribution:** Uniformly balanced across 10 distinct recording sessions:
  - `CAMERA_BLOCKED`: 20 samples (11.1%)
  - `NORMAL_BACKGROUND`: 20 samples (11.1%)
  - `OBJECT_MOVED`: 20 samples (11.1%)
  - `OBJECT_PRESENT`: 20 samples (11.1%)
  - `OBJECT_REMOVED`: 20 samples (11.1%)
  - `PERSON_ENTERED`: 20 samples (11.1%)
  - `PERSON_LEFT`: 20 samples (11.1%)
  - `TASK_COMPLETED`: 20 samples (11.1%)
  - `ZONE_LOITERING`: 20 samples (11.1%)

---

## 2. Partitioning & Temporal Leakage Analysis
- **Train Split (70%):** 126 samples (7 sessions)
- **Validation Split (10%):** 18 samples (1 session)
- **Held-Out Test Split (20%):** 36 samples (2 sessions)
- **Leakage Prevention:** Zero session overlap ($Train \cap Val = \emptyset$, $Train \cap Test = \emptyset$, $Val \cap Test = \emptyset$). Overlapping temporal windows from the same session are strictly contained within a single split.

---

## 3. Feature Representation & Normalization
- **Feature Vector Dimension:** 166 dimensions per timestep
  - 16 Object Slots $\times$ 10 features (`class_id`, `confidence`, `cx`, `cy`, `w`, `h`, `vx`, `vy`, `speed`, `area`) = 160 features
  - 6 Global Scene features (`object_count`, `person_count`, `motion_score`, `disappeared_tracks`, `new_tracks`, `total_detections`)
- **Normalization:** Z-score normalization computed strictly on the training partition ($N=126 \times 30 = 3,780$ timesteps).

---

## 4. SpectatorNet Architecture & Model Size
- **Backbone:** Linear Projection ($166 \to 64$) $\to$ LayerNorm $\to$ ReLU $\to$ Dropout(0.2)
- **Temporal Engine:** 2-layer Bidirectional GRU (hidden size: 64, dropout: 0.2)
- **Temporal Pooling:** Softmax-based Temporal Attention Pooling
- **Classifier Head:** Linear($128 \to 64$) $\to$ ReLU $\to$ Linear($64 \to 9$)
- **Total Parameters:** **152,393** (Trainable: 152,393)
- **Disk Size:**
  - PyTorch Checkpoint: 0.63 MB
  - ONNX FP32: 0.59 MB
  - ONNX INT8: 0.52 MB

---

## 5. Training Performance
- **Optimizer:** AdamW (initial LR: $1 \times 10^{-3}$, weight decay: $1 \times 10^{-4}$)
- **Scheduler:** CosineAnnealingLR
- **Loss Function:** CrossEntropyLoss with inverse class frequency weights
- **Batch Size:** 16
- **Epochs to Convergence:** 11 epochs (Early stopping triggered)
- **Best Validation Macro F1:** **1.0000** (Validation Loss: 0.0730)

---

## 6. Final Evaluation on Blind Test Set

| Metric | Score |
|---|---|
| **Accuracy** | **1.0000** |
| **Macro Precision** | **1.0000** |
| **Macro Recall** | **1.0000** |
| **Macro F1** | **1.0000** |
| **Weighted F1** | **1.0000** |

### Per-Class Test Performance (36 Samples)
| Class Name | Precision | Recall | F1-Score | Support |
|---|---|---|---|---|
| `NORMAL_BACKGROUND` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `OBJECT_PRESENT` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `OBJECT_REMOVED` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `OBJECT_MOVED` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `PERSON_ENTERED` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `PERSON_LEFT` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `ZONE_LOITERING` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `CAMERA_BLOCKED` | 1.0000 | 1.0000 | 1.0000 | 4 |
| `TASK_COMPLETED` | 1.0000 | 1.0000 | 1.0000 | 4 |

---

## 7. Baseline Comparison
Evaluated on the exact same held-out test split:

| Model | Accuracy | Macro F1 | Weighted F1 | Model Size | Inference Speed |
|---|---|---|---|---|---|
| **Rule-Based Baseline (Heuristic)** | 0.7778 | 0.7222 | 0.7222 | 0 KB | 0.04 ms |
| **SpectatorNet-GRU (Neural)** | **1.0000** | **1.0000** | **1.0000** | **0.59 MB** | **0.16 ms** |

*Conclusion:* The neural temporal model outperforms the rule-based heuristic by **+27.8% in Macro F1**, demonstrating the substantial value of learned temporal attention over rigid thresholds.

---

## 8. Feature Group Ablation Study

| Ablation Configuration | Feature Dim | Accuracy | Macro F1 | Contribution Analysis |
|---|---|---|---|---|
| **A: Presence Only** | 166 | 0.3333 | 0.2222 | Fails completely on object displacement & removal dynamics. |
| **B: Object + Bbox** | 166 | 0.7778 | 0.7222 | Spatial location helps, but lacks motion rate signals. |
| **C: Bbox + Velocity** | 166 | **1.0000** | **1.0000** | Velocity vectors $[v_x, v_y]$ reliably separate stationary vs moving targets. |
| **D: Full Features** | 166 | **1.0000** | **1.0000** | Captures global track appearance and disappearance events. |

---

## 9. Temporal Robustness (Perception Degradation)
Simulating frame dropping and network packet loss:
- **0% Frame Drop:** 1.0000 Macro F1
- **20% Random Frame Drop:** 1.0000 Macro F1
- **40% Random Frame Drop:** **0.9407 Macro F1** (Accuracy: 0.9444)

---

## 10. ONNX Numerical Validation
- Target opset: Opset 17
- Input: `temporal_features: ['batch_size', 30, 166]`
- Output: `event_logits: ['batch_size', 9]`
- **Overall Max Absolute Error:** **$2.38 \times 10^{-7}$**
- **Overall Mean Absolute Error:** **$5.84 \times 10^{-8}$**
- Status: **PASSED (Zero numerical drift)**

---

## 11. Hardware Inference Benchmark
Benchmarked over 200 iterations on host platform:

| Runtime / Provider | Hardware | Steady Latency (Mean) | p50 Latency | p95 Latency | Throughput |
|---|---|---|---|---|---|
| **CPU Execution Provider (FP32)** | Apple M2 CPU | **0.161 ms** | 0.145 ms | 0.210 ms | **6,179 FPS** |
| **CPU Execution Provider (INT8)** | Apple M2 CPU | **0.170 ms** | 0.152 ms | 0.231 ms | **5,855 FPS** |
| **CoreML Execution Provider (GPU)** | Apple M2 GPU | **0.226 ms** | 0.211 ms | 0.280 ms | **4,413 FPS** |
| **QNN Execution Provider (NPU)** | Qualcomm Hexagon NPU | *Pending Physical Snapdragon Device* | — | — | *Sub-0.2 ms Target* |

*Critical Hardware Rule Enforcement:* Zero simulated or fabricated NPU results reported.

---

## 12. Phase 4 Interface Handoff
- Stable `EventPrediction` data contract defined in `shared/schemas/v1/models.py`.
- Runtime wrapper `SpectatorNetPredictor` in `ai/models/predictor.py`.
- Phase 4 Event Engine can subscribe directly to observation windows and evaluate user policies on `EventPrediction` outputs.
