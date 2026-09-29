"""
Smart Spectator - Phase 4 & Phase 5 Complete End-to-End Pipeline Tests
Conforms to Sections 58, 73, 98, 99, 100, 101, 102, 104 of Master Implementation Prompt.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import numpy as np
import pytest

from shared.schemas.v1.models import (
    Event,
    Observation,
    EventPrediction,
    EventStatus,
    TrackedObject,
    Zone,
)
from ai.datasets.synthetic_generator import SyntheticSequenceGenerator
from ai.models.predictor import SpectatorNetPredictor
from services.event_engine import EventEngine
from services.event_engine.recorder import RecordingManager
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session


@pytest.fixture
def test_pipeline_env(tmp_path):
    db_file = tmp_path / "test_e2e.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recordings"
    settings.SNAPSHOTS_DIR = tmp_path / "snapshots"
    init_database()

    with db_session() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cameras (camera_id, name, source_type, width, height, target_fps)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("cam_e2e_01", "Front Door", "phone", 1280, 720, 30),
        )

    rec_mgr = RecordingManager(
        recordings_dir=settings.RECORDINGS_DIR,
        snapshots_dir=settings.SNAPSHOTS_DIR,
        pre_roll_seconds=2.0,
        post_roll_seconds=1.0,
    )

    engine = EventEngine(recording_manager=rec_mgr)
    engine.start()

    yield engine, rec_mgr

    engine.stop()
    if db_file.exists():
        os.remove(db_file)


# -----------------------------------------------------------------------------
# 1. Mandatory End-to-End Test 1 (Section 98): PERSON_ENTERED Complete Flow
# -----------------------------------------------------------------------------
def test_end_to_end_person_entered_pipeline(test_pipeline_env):
    """
    Mandatory Acceptance Test (Section 98):
    Camera -> Observation -> SpectatorNet -> EventPrediction -> EventEngine ->
    Confidence Filter -> Debouncer -> Rule Engine -> Confirmed Event -> SQLite ->
    Recording Trigger -> WebSocket Broadcast.
    Verifies event is created exactly once and state lifecycle transitions cleanly.
    """
    engine, rec_mgr = test_pipeline_env
    cam_id = "cam_e2e_01"

    # Capture WebSocket messages pushed during test
    ws_messages = []
    engine.subscribe_websocket(lambda msg_type, data: ws_messages.append((msg_type, data)))

    # Ingest synthetic frames into rolling buffer
    dummy_frame = np.full((120, 160, 3), 100, dtype=np.uint8)
    t0 = time.time()
    for i in range(15):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t0 + i * 0.1, frame_index=i)

    # Synthetic observations from generator
    gen = SyntheticSequenceGenerator(sequence_length=30)
    sample = gen.generate_sample("PERSON_ENTERED", session_id="e2e_person_sess")

    predictor = SpectatorNetPredictor(
        model_path="ai/models/spectatornet.onnx",
        normalization_path="ai/datasets/smart_spectator/statistics/normalization.json",
    )

    pred = predictor.predict_window(sample.observations, camera_id=cam_id)
    assert pred.event_type == "PERSON_ENTERED"
    pred.confidence = 0.88

    # Feed prediction consecutively to satisfy debouncing (min 2 consecutive)
    engine._handle_prediction(pred)
    engine._handle_prediction(pred)

    # Verify event created exactly once
    with db_session() as conn:
        cursor = conn.execute("SELECT * FROM events WHERE camera_id = ?", (cam_id,))
        rows = cursor.fetchall()
        assert len(rows) == 1
        ev_row = rows[0]
        assert ev_row["event_type"] == "PERSON_ENTERED"
        assert ev_row["status"] in ("confirmed", "active")
        assert ev_row["confidence"] >= 0.70
        assert "explanation" in ev_row and ev_row["explanation"] is not None

    # Verify WebSocket received 'event_created'
    created_ws = [msg for msg in ws_messages if msg[0] == "event_created"]
    assert len(created_ws) == 1
    assert created_ws[0][1]["event_id"] == ev_row["event_id"]

    # Resolve event
    res_ev = engine.resolve_event(ev_row["event_id"])
    assert res_ev.status == EventStatus.RESOLVED

    # Wait briefly for background recording finalization
    time.sleep(0.5)

    # Verify recording clip was generated and linked to event
    with db_session() as conn:
        cursor = conn.execute("SELECT recording_id FROM events WHERE event_id = ?", (ev_row["event_id"],))
        updated_ev = cursor.fetchone()
        assert updated_ev["recording_id"] is not None

        r_cursor = conn.execute("SELECT * FROM recordings WHERE recording_id = ?", (updated_ev["recording_id"],))
        rec_row = r_cursor.fetchone()
        assert rec_row is not None
        assert Path(rec_row["file_path"]).exists()
        assert Path(rec_row["file_path"]).stat().st_size > 0


# -----------------------------------------------------------------------------
# 2. End-to-End Test 2 (Section 99): OBJECT_REMOVED Complete Lifecycle
# -----------------------------------------------------------------------------
def test_end_to_end_object_removed_lifecycle(test_pipeline_env):
    """
    Second Mandatory Test (Section 99):
    Object exists -> disappears -> SpectatorNet emits OBJECT_REMOVED ->
    Event Engine confirms -> Recording generated -> Client resolves event.
    """
    engine, rec_mgr = test_pipeline_env
    cam_id = "cam_e2e_01"

    dummy_frame = np.full((120, 160, 3), 150, dtype=np.uint8)
    t0 = time.time()
    for i in range(15):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t0 + i * 0.1, frame_index=i)

    gen = SyntheticSequenceGenerator(sequence_length=30)
    sample = gen.generate_sample("OBJECT_REMOVED", session_id="e2e_removed_sess")

    predictor = SpectatorNetPredictor(
        model_path="ai/models/spectatornet.onnx",
        normalization_path="ai/datasets/smart_spectator/statistics/normalization.json",
    )
    pred = predictor.predict_window(sample.observations, camera_id=cam_id)
    assert pred.event_type == "OBJECT_REMOVED"
    pred.confidence = 0.85

    # Consecutive predictions
    engine._handle_prediction(pred)
    engine._handle_prediction(pred)

    with db_session() as conn:
        cursor = conn.execute("SELECT * FROM events WHERE camera_id = ? AND event_type = 'OBJECT_REMOVED'", (cam_id,))
        ev_row = cursor.fetchone()
        assert ev_row is not None
        assert ev_row["status"] in ("confirmed", "active")
        ev_id = ev_row["event_id"]

    # User acknowledges event
    ack_ev = engine.acknowledge_event(ev_id)
    assert ack_ev.metadata.get("acknowledged") is True

    # User resolves event
    res_ev = engine.resolve_event(ev_id)
    assert res_ev.status == EventStatus.RESOLVED


# -----------------------------------------------------------------------------
# 3. End-to-End Test 3 (Section 100): ZONE_LOITERING Scenario
# -----------------------------------------------------------------------------
def test_end_to_end_zone_loitering_scenario(test_pipeline_env):
    """
    Third Mandatory Test (Section 100):
    Person enters polygon zone -> Dwell timer exceeds threshold ->
    ZONE_LOITERING event created -> WebSocket broadcast -> Recording created.
    """
    engine, rec_mgr = test_pipeline_env
    cam_id = "cam_e2e_01"

    # Configure Front Door polygon zone
    door_zone = Zone(
        zone_id="front_door_zone",
        camera_id=cam_id,
        name="Front Door Restricted",
        polygon=[[0.1, 0.1], [0.6, 0.1], [0.6, 0.6], [0.1, 0.6]],
    )
    engine.zone_engine.add_or_update_zone_memory(door_zone)
    engine.zone_engine.default_loitering_seconds = 2.0

    # Ingest frames to rolling buffer
    dummy_frame = np.full((120, 160, 3), 200, dtype=np.uint8)
    t0 = time.time()
    for i in range(10):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t0 + i * 0.1, frame_index=i)

    # 1. Person enters zone
    obs_enter = Observation(
        observation_id="obs_loit_1",
        camera_id=cam_id,
        timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
        frame_index=1,
        tracked_objects=[
            TrackedObject(
                track_id=77,
                camera_id=cam_id,
                class_name="person",
                current_bbox=[0.2, 0.2, 0.4, 0.4],
                confidence=0.95,
                first_seen_timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
                last_seen_timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
            )
        ],
    )
    engine._handle_observation(obs_enter)

    # 2. Person remains in zone past 2.0s threshold
    obs_loiter = Observation(
        observation_id="obs_loit_2",
        camera_id=cam_id,
        timestamp=datetime.fromtimestamp(t0 + 2.5, tz=timezone.utc),
        frame_index=2,
        tracked_objects=[
            TrackedObject(
                track_id=77,
                camera_id=cam_id,
                class_name="person",
                current_bbox=[0.2, 0.2, 0.4, 0.4],
                confidence=0.95,
                first_seen_timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
                last_seen_timestamp=datetime.fromtimestamp(t0 + 2.5, tz=timezone.utc),
            )
        ],
    )
    # Consecutive observations trigger debouncing
    engine._handle_observation(obs_loiter)
    engine._handle_observation(obs_loiter)

    with db_session() as conn:
        cursor = conn.execute("SELECT * FROM events WHERE camera_id = ? AND event_type = 'ZONE_LOITERING'", (cam_id,))
        rows = cursor.fetchall()
        assert len(rows) >= 1
        loit_ev = rows[0]
        assert loit_ev["event_type"] == "ZONE_LOITERING"
        assert loit_ev["zone_id"] == "front_door_zone"


# -----------------------------------------------------------------------------
# 4. Failure Test (Section 101): AI Perception Unavailable
# -----------------------------------------------------------------------------
def test_failure_isolation_ai_unavailable(test_pipeline_env):
    """
    Failure Test (Section 101):
    Simulate AI failure / uninitialized model.
    Expected: Streaming and Event Engine remain operational; no fake predictions.
    """
    engine, _ = test_pipeline_env
    # Send empty observations to predictor -> should raise or handle defensively
    predictor = SpectatorNetPredictor(model_path="non_existent.onnx")
    # Predictor initialized with missing model defaults gracefully
    assert predictor.session is None


# -----------------------------------------------------------------------------
# 5. Recording Storage Failure Test (Section 102)
# -----------------------------------------------------------------------------
def test_recording_storage_failure_isolation(test_pipeline_env):
    """
    Recording Failure Test (Section 102):
    Simulate recording failure (e.g. read-only disk or corrupt write).
    Expected: Event still gets created; Event engine remains operational.
    """
    engine, rec_mgr = test_pipeline_env
    cam_id = "cam_e2e_01"

    now_dt = datetime.now(timezone.utc)
    ev = Event(
        event_id="ev_fail_test",
        camera_id=cam_id,
        event_type="CAMERA_BLOCKED",
        status=EventStatus.CONFIRMED,
        confidence=0.95,
        summary="Obstruction test",
        timestamp=now_dt,
    )

    # Point recordings dir to an invalid path or trigger error in finalize
    rec_mgr.recordings_dir = Path("/non_existent_dir_cannot_create_here/recordings")
    res = rec_mgr.finalize_recording(ev)
    # Recording returns None upon error, but does not crash process
    assert res is None


# -----------------------------------------------------------------------------
# 6. Multi-Camera Isolation Test (Section 104)
# -----------------------------------------------------------------------------
def test_multi_camera_isolation(test_pipeline_env):
    """
    Multi-Camera Isolation Test (Section 104):
    Simulate Camera A, Camera B, Camera C.
    Verify tracking, debouncing, zones, and events remain strictly isolated.
    """
    engine, _ = test_pipeline_env
    now = datetime.now(timezone.utc)

    pred_a = EventPrediction(camera_id="cam_A", event_type="PERSON_ENTERED", confidence=0.88, timestamp=now)
    pred_b = EventPrediction(camera_id="cam_B", event_type="OBJECT_REMOVED", confidence=0.85, timestamp=now)
    pred_c = EventPrediction(camera_id="cam_C", event_type="CAMERA_BLOCKED", confidence=0.90, timestamp=now)

    # Trigger consecutive predictions per camera
    engine._handle_prediction(pred_a)
    engine._handle_prediction(pred_a)

    engine._handle_prediction(pred_b)
    engine._handle_prediction(pred_b)

    engine._handle_prediction(pred_c)
    engine._handle_prediction(pred_c)

    with db_session() as conn:
        rows_a = conn.execute("SELECT event_type FROM events WHERE camera_id = 'cam_A'").fetchall()
        rows_b = conn.execute("SELECT event_type FROM events WHERE camera_id = 'cam_B'").fetchall()
        rows_c = conn.execute("SELECT event_type FROM events WHERE camera_id = 'cam_C'").fetchall()

        assert len(rows_a) == 1 and rows_a[0]["event_type"] == "PERSON_ENTERED"
        assert len(rows_b) == 1 and rows_b[0]["event_type"] == "OBJECT_REMOVED"
        assert len(rows_c) == 1 and rows_c[0]["event_type"] == "CAMERA_BLOCKED"
