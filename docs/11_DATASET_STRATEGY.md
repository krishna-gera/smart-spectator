# Smart Spectator — Dataset Strategy & Data Engineering

**Document ID:** `SS-DOC-011`  
**Phase:** Phase 0 (Architecture & Foundation)  
**Status:** Approved  

---

## 1. Role of Datasets in Smart Spectator

Smart Spectator utilizes a dual dataset strategy:
1. **Public Benchmark Datasets:** Used for pre-training feature backbones, establishing baseline object detectors (Level 1), and benchmarking temporal feature representations.
2. **The Smart Spectator Proprietary Dataset:** Engineered specifically to train and evaluate **SpectatorNet** (Level 3) on real-world, desk-scale, and room-scale temporal event transitions captured by mobile phone cameras.

---

## 2. Public Dataset Research & Alignment

| Dataset | Primary Domain | Applicability to Smart Spectator | Strategic Utilization |
| :--- | :--- | :--- | :--- |
| **MS COCO** | 80 Object Classes | Object detection pre-training | Base weights for Level 1 Spatial Detector (YOLOv8n). |
| **Something-Something v2** | 220k Video Clips | Fine-grained object interactions | Pre-training temporal interaction heads ("moving X", "taking X"). |
| **UCF101 / Kinetics-400** | Human Action Recognition | Coarse human motion | Pre-training temporal video backbones for action priors. |
| **ShanghaiTech Campus** | Surveillance Anomaly | Fixed camera anomalies | Benchmarking anomaly detection and camera obstruction baselines. |
| **UCF-Crime** | Real-world Surveillance | Security event triggers | Evaluating edge-case security triggers (loitering, intrusion). |

---

## 3. The Smart Spectator Dataset Specification

The Smart Spectator Dataset is curated using actual Android smartphone camera nodes to ensure the visual domain matches production deployments (e.g., lens distortion, auto-focus breathing, noise characteristics of mobile sensors).

### 3.1 Dataset Scale & Distribution
- **Total Video Clips:** 6,000 curated temporal sequences.
- **Clip Duration:** Fixed sliding windows of 3.2 seconds ($T = 16$ frames at 5 FPS sampling rate).
- **Target Distribution Across Classes:**
  - `OBJECT_REMOVED`: 1,000 clips
  - `OBJECT_MOVED`: 800 clips
  - `PERSON_ENTERED`: 1,000 clips
  - `PERSON_LEFT`: 800 clips
  - `ZONE_LOITERING`: 600 clips
  - `CAMERA_BLOCKED`: 400 clips
  - `TASK_COMPLETED`: 400 clips
  - `NORMAL_BACKGROUND`: 1,000 clips

### 3.2 Partitioning Scheme
- **Training Set (70%):** 4,200 clips (used for model optimization).
- **Validation Set (15%):** 900 clips (used for hyperparameter tuning & early stopping).
- **Test Set (15%):** 900 clips (held-out blind evaluation; strictly zero scene or actor overlap with training set).

---

## 4. Diversity Matrix & Environmental Variations

To ensure robust generalization across homes, offices, and workshops, data collection enforces a strict multi-dimensional diversity matrix:

```
[ Visual Diversity Dimensions ]
├── 1. Lighting Conditions
│   ├── Bright daylight (500-1000 lux)
│   ├── Warm artificial indoor lighting (200-400 lux)
│   ├── Low-light / evening ambient (10-50 lux)
│   └── Backlit glare / high dynamic range (window background)
│
├── 2. Camera Placement & Angles
│   ├── Desk level (30-60 cm height, front-facing)
│   ├── Shelf / counter level (1.2-1.5m height, 30° downward angle)
│   └── Elevated wall / corner mount (2.2-2.5m height, 45° downward angle)
│
├── 3. Distance & Scale
│   ├── Near field (0.5m - 1.5m, personal desk objects)
│   ├── Mid field (1.5m - 4.0m, room interior)
│   └── Far field (4.0m - 8.0m, entryway / hallway)
│
└── 4. Occlusion & Noise
    ├── Partial object occlusion (hands, passing bodies, laptops)
    ├── Mobile auto-focus hunting & camera micro-vibrations
    └── Complex cluttered backgrounds
```

---

## 5. Annotation Schema & Tooling

Annotations are serialized in a standard JSON format linking temporal event windows with spatial bounding boxes and tracklet IDs.

### 5.1 JSON Annotation Format
```json
{
  "sequence_id": "seq_2026_09_29_0042",
  "fps": 5.0,
  "frame_count": 16,
  "camera_metadata": {
    "sensor_model": "Sony IMX787 (Pixel 7 Pro)",
    "resolution": [1280, 720],
    "lighting_lux": 320,
    "environment": "home_office"
  },
  "temporal_event": {
    "event_class": "OBJECT_REMOVED",
    "event_start_frame": 6,
    "event_end_frame": 12,
    "confidence": 1.0,
    "target_class": "bottle",
    "target_track_id": 3
  },
  "frames": [
    {
      "frame_index": 0,
      "timestamp_ms": 0,
      "detections": [
        {
          "track_id": 3,
          "class_name": "bottle",
          "bbox_norm": [0.42, 0.55, 0.49, 0.72]
        }
      ]
    }
  ]
}
```

### 5.2 Version Control & Lineage
Dataset artifacts, raw video archives, and JSON ground-truth manifests are version-controlled using **DVC (Data Version Control)** paired with local storage caches.
- `ai/datasets/manifests/v1.0.0.json`: Canonical checksummed manifest for reproducible training runs.
