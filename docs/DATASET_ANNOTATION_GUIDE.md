# Smart Spectator — Dataset Annotation & Curation Guide

**Document ID:** `SS-DOC-021`  
**Phase:** Phase 3 (Data Engineering)  
**Status:** Approved  

---

## 1. Dataset Purpose

The Smart Spectator Dataset is curated to train and benchmark temporal event intelligence models (specifically **SpectatorNet**). It captures subtle state transitions (e.g. object removal, movement, zone loitering, camera blocking) from mobile camera streams over sliding temporal windows.

---

## 2. Event Taxonomy & Operational Definitions

To eliminate subjective human bias during annotation, every event class adheres to a strict, unambiguous operational definition:

| Event Label | Label ID | Operational Definition | Negative Examples / Clarifications |
|---|---|---|---|
| **`NORMAL_BACKGROUND`** | 0 | Ambient environment with no active human-object interaction or state changes. May include stationary furniture, empty rooms, or steady background lighting. | A person walking past without stopping or interacting is `PERSON_ENTERED`/`PERSON_LEFT`, not `NORMAL_BACKGROUND`. |
| **`OBJECT_PRESENT`** | 1 | Monitored item (cup, keys, backpack, laptop) remains stationary in its designated location throughout the entire sequence. | If the object was placed during this sequence, label as `TASK_COMPLETED`. |
| **`OBJECT_REMOVED`** | 2 | An item previously stationary and tracked in the scene is taken away and is no longer present in the frame at the end of the sequence. | If the object is simply moved to a different spot on the table, label as `OBJECT_MOVED`. |
| **`OBJECT_MOVED`** | 3 | An item is displaced from its initial coordinates to a new location within the frame, remaining visible at sequence end. | If the object is carried out of the camera field of view, label as `OBJECT_REMOVED`. |
| **`PERSON_ENTERED`** | 4 | No person was visible in the initial 20% of the sequence; a person enters the camera field of view and remains visible. | If the person was already present at $t=0$, do NOT label as `PERSON_ENTERED`. |
| **`PERSON_LEFT`** | 5 | A person visible in the initial 50% of the sequence moves completely out of the frame and remains absent at $t=29$. | If the person briefly steps behind a chair but returns, label as `ZONE_LOITERING`. |
| **`ZONE_LOITERING`** | 6 | A person remains within a concentrated spatial zone for the majority of the sequence with minimal displacement ($< 0.05$ normalized velocity). | Fast transit across the room is `PERSON_ENTERED`/`PERSON_LEFT`. |
| **`CAMERA_BLOCKED`** | 7 | The camera view is obstructed (hand placed over lens, turned toward wall, extreme glare/blackout) causing sudden loss of visual structure. | Gradual room light dimming is NOT camera blocked. |
| **`TASK_COMPLETED`** | 8 | A multi-action sequence where an actor completes a defined placement or interaction (e.g. placing down mug, releasing it, and withdrawing hands). | Simply touching an object without releasing it is not completed. |

---

## 3. Sequence & Clip Standards
- **Sequence Length:** Exactly **30 observation frames**.
- **Sampling Frequency:** **5.0 FPS** (approximately $6.0$ seconds total duration).
- **Coordinate System:** All bounding boxes MUST be normalized float coordinates $[x_{\min}, y_{\min}, x_{\max}, y_{\max}] \in [0.0, 1.0]$.
- **Max Objects per Timestep:** Up to 16 tracked objects. If $> 16$ objects exist, deterministic ranking by $(confidence \times area)$ retains the primary 16.

---

## 4. Exclusion & Rejection Rules
A recording must be excluded if:
1. Frame rate drops below 2.0 FPS for more than 5 consecutive frames.
2. Lens flare or camera defocus corrupts $> 50\%$ of the active frame area without intentional blocking.
3. Severe camera physical drop or shake occurs unless specifically annotating camera tampering.

---

## 5. Temporal Leakage Prevention Policy
- **Rule:** Overlapping temporal windows extracted from the same recording session MUST NEVER be partitioned across different splits.
- **Enforcement:** The dataset splitter (`ai/datasets/split.py`) groups samples by `session_id`. All sliding windows derived from `session_042` belong entirely to `train`, `val`, or `test`.
- **Validation:** `scripts/validate_dataset.py` enforces zero intersection between partition session sets before training commences.
