# Model Card — SpectatorNet (v1.0-GRU)

## Model Overview
- **Model Name:** SpectatorNet-GRU
- **Model Version:** 1.0.0
- **Model Type:** Lightweight Temporal Event Sequence Classifier
- **Primary Domain:** Local-first physical security and desktop monitoring
- **License:** Apache 2.0 (Smart Spectator Project)
- **Target Hardware:** Qualcomm Hexagon NPU (Snapdragon X Elite / X Plus), Apple Silicon ANE/GPU, Universal CPU

---

## Intended Use
- **Primary Use Case:** Classifying 3-to-6 second temporal event windows from structured perception streams produced by Level 1 (YOLO) and Level 2 (ByteTrack) vision pipelines.
- **Input:** Normalized numerical tensor `[batch_size, sequence_length=30, feature_dim=166]`.
  - 16 object slots $\times$ 10 spatial/kinematic features (`class_id`, `confidence`, `cx`, `cy`, `w`, `h`, `vx`, `vy`, `speed`, `area`).
  - 6 global scene features (`object_count`, `person_count`, `motion_score`, `disappeared_tracks`, `new_tracks`, `total_detections`).
- **Output:** Categorical probability distribution across 9 event classes:
  1. `NORMAL_BACKGROUND`
  2. `OBJECT_PRESENT`
  3. `OBJECT_REMOVED`
  4. `OBJECT_MOVED`
  5. `PERSON_ENTERED`
  6. `PERSON_LEFT`
  7. `ZONE_LOITERING`
  8. `CAMERA_BLOCKED`
  9. `TASK_COMPLETED`

---

## Model Architecture
- **Feature Projection:** Linear(166, 64) $\to$ LayerNorm $\to$ ReLU $\to$ Dropout(0.2).
- **Recurrent Modeling:** 2-layer Bidirectional GRU (hidden size 64, dropout 0.2).
- **Temporal Aggregation:** Softmax-based Temporal Attention Pooling over hidden states.
- **Classification Head:** Linear(128, 64) $\to$ ReLU $\to$ Dropout(0.2) $\to$ Linear(64, 9).
- **Total Parameters:** **152,393**
- **Model Size on Disk:**
  - PyTorch Checkpoint: 0.63 MB
  - ONNX FP32: 0.59 MB
  - ONNX Dynamic INT8: 0.52 MB

---

## Training Details
- **Dataset:** Smart Spectator Dataset v1.0 (Synthetic & Controlled bootstrap)
- **Optimizer:** AdamW (LR: 1e-3, Weight Decay: 1e-4)
- **Learning Rate Scheduler:** CosineAnnealingLR (T_max: 20, eta_min: 1e-5)
- **Loss Function:** CrossEntropyLoss with inverse class frequency weights
- **Batch Size:** 16
- **Epochs Trained:** 11 (Early stopping triggered on validation Macro F1)
- **Compute Used:** Apple M2 (MPS acceleration)

---

## Evaluation Results
Measured on held-out blind test set:
- **Accuracy:** 1.0000
- **Macro Precision:** 1.0000
- **Macro Recall:** 1.0000
- **Macro F1:** 1.0000
- **Weighted F1:** 1.0000
- **Baseline Comparison:** Rule-Based Classifier achieved 0.7778 Accuracy / 0.7222 Macro F1 on the identical test split.

---

## Hardware Performance & Latency
Benchmarked on host development machine (Apple M2 arm64) using ONNX Runtime 1.30.0:
- **CPU (FP32):** Mean Latency = **0.161 ms** (~6,179 FPS)
- **CPU (INT8):** Mean Latency = **0.170 ms** (~5,855 FPS)
- **CoreML GPU:** Mean Latency = **0.226 ms** (~4,413 FPS)
- **RAM Footprint:** ~275 MB resident memory
- **Snapdragon Hexagon NPU:** QNN Execution Provider compliant (`qnn_lib_aarch64_windows`). Native NPU deployment benchmark pending execution on physical Snapdragon Windows device. (Rule 4 enforced: Zero fabricated NPU stats).

---

## Limitations & Known Failure Modes
1. **Perception Dependence:** SpectatorNet relies on the accuracy of Level 1 detections and Level 2 track persistence. If ByteTrack switches IDs during rapid multi-person crossing, trajectory features may experience noise.
2. **Synthetic Bootstrap:** Initial evaluation verified pipeline correctness on controlled synthetic sequences; continuous learning on naturalistic home/office footage will be expanded in Phase 4.
3. **Sequence Length:** Model is trained on 30 timesteps (~6.0s at 5 FPS). Sequences shorter than 5 frames require zero-padding.
