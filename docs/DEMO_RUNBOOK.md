# Smart Spectator Demonstration Runbook

This runbook guides operators and presenters through executing deterministic demonstration scenarios for the **Snapdragon AI Lab Build & Present Challenge**.

---

## 1. Quick Demonstration Launch

To run the automated, deterministic end-to-end demonstration harness:
```bash
python3 scripts/run_demo.py
```
To run multi-scenario automated test assertions:
```bash
python3 scripts/demo_scenarios.py
```

---

## 2. Real-Device Demonstration Scenarios

### Scenario 1: Person Enters Monitored Area (`PERSON_ENTERED`)
- **Setup**: Android camera phone positioned facing an entrance doorway or conference room entry. An entry zone polygon is drawn on the monitoring dashboard.
- **Action**: A person walks through the doorway into the camera frame and pauses for 1–2 seconds.
- **Expected Observation**:
  - YOLOv8n detects `person` class with bounding box coordinates.
  - ByteTrack assigns a persistent trajectory ID (e.g., `track_id=1`).
- **Expected Event**:
  - `PERSON_ENTERED` event confirmed with confidence $> 0.70$.
  - Severity: `MEDIUM`.
- **Expected Recording**:
  - Clip synthesized at `recordings/event_evt_*.mp4`.
  - Captures 5.0 seconds of pre-roll before the person crossed the threshold.
- **Dashboard Behavior**:
  - Event alert banner illuminates on the monitoring timeline.
  - Bounding box renders with person class label on the live video tile.

---

### Scenario 2: Object Removed (`OBJECT_REMOVED`)
- **Setup**: A desk zone is created containing a laptop or backpack resting on a table.
- **Action**: An individual approaches the desk, picks up the object, and walks out of the frame with it.
- **Expected Observation**:
  - Detector tracks both the person and the object simultaneously.
  - Object tracklet status changes from active to inactive while in close proximity to the person tracklet.
- **Expected Event**:
  - SpectatorNet GRU classifies the interaction transition as `OBJECT_REMOVED`.
  - Confidence: $> 0.65$.
  - Severity: `HIGH`.
- **Expected Recording**:
  - Generates clip showing the approach, the pick-up, and departure with 5-second pre-roll context.
- **Dashboard Behavior**:
  - High-priority red notification card rendered on event timeline.
  - Snapshot shows exact location of object prior to removal.

---

### Scenario 3: Object Moved (`OBJECT_MOVED`)
- **Setup**: Monitored desk or counter zone containing a target object.
- **Action**: A person picks up the object, relocates it across the desk (within frame), and releases it.
- **Expected Observation**:
  - Persistent tracklet ID shifts coordinates from source $(x_1, y_1)$ to target $(x_2, y_2)$ beyond the motion threshold.
- **Expected Event**:
  - SpectatorNet correlates displacement transition as `OBJECT_MOVED`.
  - Severity: `LOW` or `MEDIUM`.
- **Expected Recording**:
  - Video clip captures the transfer motion smoothly.
- **Dashboard Behavior**:
  - Event item added to history; no critical alarm sounded.

---

### Scenario 4: Person Loitering in Zone (`ZONE_LOITERING`)
- **Setup**: High-security zone drawn around a doorway or server rack. Rule configured with `dwell_time_seconds = 5.0`.
- **Action**: A person enters the polygon zone and remains stationary inside for over 5 seconds.
- **Expected Observation**:
  - ByteTrack tracks centroid coordinates inside the polygon for $\ge 150$ consecutive video frames.
- **Expected Event**:
  - Rule engine evaluates dwell duration threshold and emits `ZONE_LOITERING`.
  - Severity: `HIGH`.
- **Expected Recording**:
  - MP4 recording generated covering entire loitering interval plus 5.0s pre-roll.
- **Dashboard Behavior**:
  - Polygon zone flashes amber on the operator canvas; chime alert triggers.

---

### Scenario 5: Camera Obstructed (`CAMERA_BLOCKED`)
- **Setup**: Actively streaming camera node.
- **Action**: Operator covers the phone camera lens with a notebook or hand, plunging the frame into darkness or complete blur.
- **Expected Observation**:
  - Spatial frame entropy drops precipitously; zero objects detected.
- **Expected Event**:
  - SpectatorNet classifies sequence as `CAMERA_BLOCKED` or system emits tamper alert.
  - Severity: `CRITICAL`.
- **Expected Recording**:
  - Immediate clip synthesized capturing the moment before and during obstruction.
- **Dashboard Behavior**:
  - Camera card displays "FEED OBSTRUCTED" warning badge.
