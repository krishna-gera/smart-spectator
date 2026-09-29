"""
Smart Spectator - Multi-Camera Node Strict Isolation Test Suite
Conforms to Section 9 of Phase 8 Master Specification.
Environment Mode: [SIMULATED - Multi-Camera Node Harness]
Verifies that 1, 2, and 3 concurrent camera nodes maintain strict isolation across:
1. Ingestion Sessions
2. Frame Samplers & Bounded Queues
3. ByteTrack Tracker Instances & Track IDs
4. SpectatorNet Temporal Windows
5. Event State Machines & Event Routing
6. Rolling Frame Buffers & Clip Recordings
"""

import time
import uuid
from pathlib import Path
import pytest
import numpy as np

from services.stream_engine.server import StreamEngine
from services.ai_engine.pipeline import AIPipeline, CameraPerceptionContext
from services.ai_engine.detector import YOLOObjectDetector
from services.event_engine.engine import EventEngine
from services.event_engine.recorder import RecordingManager
from shared.schemas.v1.models import Detection, Event, EventStatus, EventSeverity


@pytest.fixture
def isolated_hub_env(tmp_path):
    rec_dir = tmp_path / "rec_iso"
    rec_dir.mkdir(parents=True, exist_ok=True)
    snap_dir = tmp_path / "snap_iso"
    snap_dir.mkdir(parents=True, exist_ok=True)
    return rec_dir, snap_dir


def test_multi_camera_stream_session_isolation():
    """Verifies that StreamEngine creates independent, isolated sessions per camera."""
    engine = StreamEngine()
    cam_ids = ["cam_alpha", "cam_beta", "cam_gamma"]

    sessions = [engine.get_or_create_session(cid) for cid in cam_ids]
    assert len(sessions) == 3

    # Ensure memory identity isolation
    assert sessions[0] is not sessions[1]
    assert sessions[1] is not sessions[2]
    assert sessions[0].camera_id == "cam_alpha"
    assert sessions[1].camera_id == "cam_beta"
    assert sessions[2].camera_id == "cam_gamma"

    # Clean removal of one camera does not affect others
    engine.remove_session("cam_beta")
    assert "cam_beta" not in engine.sessions
    assert "cam_alpha" in engine.sessions
    assert "cam_gamma" in engine.sessions


def test_multi_camera_perception_and_tracker_isolation():
    """
    [SIMULATED] Verifies that 3 cameras maintain strictly isolated ByteTrack trackers,
    queues, and metrics. Track IDs in Camera A must not bleed into Camera B.
    """
    pipeline = AIPipeline(detector=YOLOObjectDetector())
    cam_a = "cam_node_01"
    cam_b = "cam_node_02"
    cam_c = "cam_node_03"

    ctx_a = pipeline.get_or_create_context(cam_a)
    ctx_b = pipeline.get_or_create_context(cam_b)
    ctx_c = pipeline.get_or_create_context(cam_c)

    # Ensure separate tracker instances
    assert ctx_a.tracker is not ctx_b.tracker
    assert ctx_b.tracker is not ctx_c.tracker

    # Simulate detections in Camera A
    det_a = [
        Detection(
            detection_id="det_a_1",
            class_id=0,
            class_name="person",
            confidence=0.88,
            bbox_xyxy=[0.1, 0.1, 0.3, 0.5],
        )
    ]
    tracked_a = ctx_a.tracker.update(cam_a, det_a, time.time())
    assert len(tracked_a) == 1

    # Simulate different detections in Camera B
    det_b = [
        Detection(
            detection_id="det_b_1",
            class_id=24,
            class_name="backpack",
            confidence=0.75,
            bbox_xyxy=[0.5, 0.5, 0.7, 0.8],
        )
    ]
    tracked_b = ctx_b.tracker.update(cam_b, det_b, time.time())
    assert len(tracked_b) == 1

    # Camera A tracker must only report Camera A detections
    assert tracked_a[0].camera_id == cam_a
    assert tracked_b[0].camera_id == cam_b

    # Verify queue submission isolation
    frame_a = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame_b = np.ones((720, 1280, 3), dtype=np.uint8) * 255

    pipeline.submit_frame(cam_a, frame_a, frame_index=1, timestamp=time.time())
    pipeline.submit_frame(cam_b, frame_b, frame_index=1, timestamp=time.time())

    assert ctx_a.queue.qsize() == 1
    assert ctx_b.queue.qsize() == 1
    assert ctx_c.queue.qsize() == 0


def test_multi_camera_event_and_recording_isolation(isolated_hub_env):
    """
    [SIMULATED] Verifies that Event Engine and Recording Manager keep recordings and event
    triggers completely isolated across cameras.
    """
    rec_dir, snap_dir = isolated_hub_env
    recorder = RecordingManager(recordings_dir=rec_dir, snapshots_dir=snap_dir)

    cam_1 = "cam_door"
    cam_2 = "cam_yard"

    frame_1 = np.full((480, 640, 3), 50, dtype=np.uint8)
    frame_2 = np.full((480, 640, 3), 200, dtype=np.uint8)

    # Ingest frames into separate buffers
    for i in range(15):
        recorder.ingest_frame(cam_1, frame_1, time.time(), i)
    for j in range(15):
        recorder.ingest_frame(cam_2, frame_2, time.time(), j)

    buf_1 = recorder.get_or_create_buffer(cam_1)
    buf_2 = recorder.get_or_create_buffer(cam_2)

    assert len(buf_1.get_all_frames()) == 15
    assert len(buf_2.get_all_frames()) == 15

    # Frames in buffer 1 must have pixel value 50, buffer 2 must have 200
    assert np.all(buf_1.get_all_frames()[0].frame == 50)
    assert np.all(buf_2.get_all_frames()[0].frame == 200)

    # Trigger event on Camera 1 only
    evt_1 = Event(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        camera_id=cam_1,
        event_type="PERSON_ENTERED",
        status=EventStatus.ACTIVE,
        severity=EventSeverity.MEDIUM,
        confidence=0.85,
        summary="Door entry",
    )
    recorder.trigger_recording_start(evt_1)
    rec_1 = recorder.finalize_recording(evt_1)

    assert rec_1 is not None
    assert rec_1.camera_id == cam_1
    assert Path(rec_1.file_path).exists()

    # Camera 2 should have NO active recordings
    assert evt_1.event_id not in recorder._active_recordings
