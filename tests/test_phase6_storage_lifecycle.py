"""
Smart Spectator - Phase 6 Storage Quota & Lifecycle Management Tests
Conforms to Sections 20 & 21 of Phase 6 Master Specification.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import numpy as np
import pytest

from shared.schemas.v1.models import Event, EventStatus, EventSeverity
from services.event_engine.recorder import RecordingManager, CameraRollingBuffer
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session


@pytest.fixture
def storage_test_env(tmp_path):
    db_file = tmp_path / "test_storage.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recs"
    settings.SNAPSHOTS_DIR = tmp_path / "snaps"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()

    with db_session() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_st_01', 'Storage Cam', 'phone')")

    rec_mgr = RecordingManager(
        recordings_dir=settings.RECORDINGS_DIR,
        snapshots_dir=settings.SNAPSHOTS_DIR,
        max_storage_gb=0.001,  # 1 MB quota for testing
        retention_days=1,
    )
    yield rec_mgr, tmp_path
    if db_file.exists():
        db_file.unlink()


def test_disk_full_threshold_marks_event_degraded(storage_test_env, monkeypatch):
    """
    Verifies that when free disk space falls below MIN_FREE_DISK_MB,
    video writing is skipped, event metadata is preserved, and degraded state is recorded (Section 21).
    """
    rec_mgr, _ = storage_test_env
    cam_id = "cam_st_01"

    # Simulate low disk space (e.g. only 100 MB free, below 500 MB threshold)
    import psutil
    class FakeDiskUsage:
        free = 100 * 1024 * 1024 # 100 MB
        total = 1000 * 1024 * 1024
        used = 900 * 1024 * 1024

    monkeypatch.setattr(psutil, "disk_usage", lambda path: FakeDiskUsage())

    # Ingest frames into buffer
    dummy_frame = np.full((100, 100, 3), 120, dtype=np.uint8)
    for i in range(10):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=time.time() + i * 0.1, frame_index=i)

    now = datetime.now(timezone.utc)
    ev = Event(
        event_id="ev_disk_full_01",
        camera_id=cam_id,
        event_type="PERSON_ENTERED",
        status=EventStatus.ACTIVE,
        severity=EventSeverity.HIGH,
        confidence=0.92,
        summary="Intrusion under disk full condition",
        timestamp=now,
    )

    # Pre-insert event in database
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO events (event_id, camera_id, event_type, status, severity, confidence, summary, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ev.event_id, ev.camera_id, ev.event_type, "active", "high", ev.confidence, ev.summary, now.isoformat())
        )

    # Finalize recording under simulated disk-full threshold
    rec = rec_mgr.finalize_recording(ev)
    # Clip write must be gracefully skipped
    assert rec is None

    # Event metadata must be updated with degraded recording status
    with db_session() as conn:
        cursor = conn.execute("SELECT metadata_json FROM events WHERE event_id = ?", (ev.event_id,))
        row = cursor.fetchone()
        meta = json.loads(row["metadata_json"])
        assert meta.get("recording_degraded") is True
        assert meta.get("recording_skipped_reason") == "disk_full_threshold"


def test_storage_quota_fifo_cleanup(storage_test_env):
    """
    Verifies that when storage exceeds quota, oldest recordings are cleaned up in FIFO order (Section 21).
    """
    rec_mgr, _ = storage_test_env
    cam_id = "cam_st_01"

    # Create 3 synthetic recording files and DB records with differing timestamps
    created_recs = []
    for i in range(3):
        rec_id = f"rec_fifo_0{i}"
        file_path = settings.RECORDINGS_DIR / f"test_clip_{i}.mp4"
        file_path.write_bytes(b"0" * 600 * 1024) # 600 KB each (3 * 600 KB = 1.8 MB > 1 MB quota)
        
        t_iso = datetime.fromtimestamp(1000.0 + i * 100, tz=timezone.utc).isoformat()
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO recordings (
                    recording_id, camera_id, file_path, start_time, end_time,
                    duration_seconds, file_size_bytes, codec, width, height, fps, created_at
                ) VALUES (?, ?, ?, ?, ?, 5.0, ?, 'h264', 640, 480, 10.0, ?)
                """,
                (rec_id, cam_id, str(file_path), t_iso, t_iso, file_path.stat().st_size, t_iso)
            )
        created_recs.append((rec_id, file_path))

    # Total size exceeds 1.0 MB quota -> trigger cleanup
    rec_mgr.cleanup_storage()

    # Oldest recording (rec_fifo_00) should be removed first from both disk and DB
    oldest_id, oldest_path = created_recs[0]
    assert not oldest_path.exists()

    with db_session() as conn:
        cur = conn.execute("SELECT COUNT(*) as c FROM recordings WHERE recording_id = ?", (oldest_id,))
        assert cur.fetchone()["c"] == 0
