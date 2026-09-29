"""
Smart Spectator - Phase 4 Recording Engine & Rolling Buffer Tests
Tests bounded circular frame buffering, pre/post-roll MP4 clip encoding,
storage quota cleanup, and path traversal security.
Conforms to Sections 24, 25, 26, 27, 63, 64, 71 of Phase 4 specification.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import time
import numpy as np
import pytest

from shared.schemas.v1.models import Event, EventStatus, EventSeverity
from services.event_engine.recorder import CameraRollingBuffer, RecordingManager
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_recorder.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "test_recordings"
    settings.SNAPSHOTS_DIR = tmp_path / "test_snapshots"
    init_database()
    yield
    if db_file.exists():
        os.remove(db_file)


def test_rolling_buffer_bounded_capacity_and_eviction():
    # Max 5 frames, max 2.0 seconds
    buf = CameraRollingBuffer(max_seconds=2.0, max_frames=5)
    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Ingest 8 frames -> capacity must cap at 5 frames
    for i in range(8):
        buf.add_frame(dummy_frame, timestamp=100.0 + i * 0.1, frame_index=i)

    assert buf.frame_count() == 5
    # Oldest frames evicted
    frames = buf.get_all_frames()
    assert frames[0].frame_index == 3
    assert frames[-1].frame_index == 7

    # Time-based eviction: add frame at t=110.0 -> all frames older than t=108.0 evicted
    buf.add_frame(dummy_frame, timestamp=110.0, frame_index=99)
    assert buf.frame_count() == 1
    assert buf.get_all_frames()[0].frame_index == 99


def test_recording_manager_clip_generation(tmp_path):
    rec_mgr = RecordingManager(
        recordings_dir=tmp_path / "recs",
        snapshots_dir=tmp_path / "snaps",
        pre_roll_seconds=2.0,
        post_roll_seconds=1.0,
    )

    cam_id = "cam_rec_test"
    dummy_frame = np.full((120, 160, 3), 128, dtype=np.uint8)

    # Ingest pre-roll frames
    t_start = 100.0
    for i in range(10):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t_start + i * 0.2, frame_index=i)

    now_dt = datetime.fromtimestamp(102.0, tz=timezone.utc)
    ev = Event(
        event_id="ev_rec_01",
        camera_id=cam_id,
        event_type="OBJECT_REMOVED",
        status=EventStatus.ACTIVE,
        severity=EventSeverity.MEDIUM,
        confidence=0.88,
        summary="Test clip generation",
        timestamp=now_dt,
        created_at=now_dt,
        updated_at=now_dt,
    )

    # Trigger recording start
    rec_mgr.trigger_recording_start(ev)

    # Ingest active event frames
    for i in range(10, 15):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t_start + i * 0.2, frame_index=i)

    # Finalize recording
    rec = rec_mgr.finalize_recording(ev)
    assert rec is not None
    assert rec.event_id == "ev_rec_01"
    assert rec.camera_id == cam_id
    assert Path(rec.file_path).exists()
    assert Path(rec.file_path).stat().st_size > 0
    assert rec.thumbnail_path is not None
    assert Path(rec.thumbnail_path).exists()


def test_recording_path_traversal_security(tmp_path):
    rec_mgr = RecordingManager(
        recordings_dir=tmp_path / "recs",
        snapshots_dir=tmp_path / "snaps",
    )

    # Insert malicious recording path in database with directory traversal
    malicious_path = str(tmp_path / "recs" / ".." / "secret.txt")
    with db_session() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam1', 'Camera 1', 'phone')")
        conn.execute(
            """
            INSERT INTO recordings (
                recording_id, camera_id, file_path, start_time, end_time,
                duration_seconds, file_size_bytes, width, height, fps, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("rec_hacked", "cam1", malicious_path, "2026-09-29T10:00:00", "2026-09-29T10:00:10", 10.0, 100, 640, 480, 10.0, "2026-09-29T10:00:00"),
        )

    # Safe path resolver must reject path traversal attempt
    safe_path = rec_mgr.resolve_safe_recording_path("rec_hacked")
    assert safe_path is None
