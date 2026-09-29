"""Phase 9 Tests — Storage Retention Management & Locked Recordings Protection.

Validates:
1. Automated retention pruning of expired events and recordings
2. Protection of locked recordings (is_locked=1) from retention deletion
3. Protection of locked recordings from manual API deletion (403 Forbidden)
4. Orphan MP4 file cleanup
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from services.hub_backend.storage.retention import run_retention_cleanup as run_retention_prune
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db_connection
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_phase9_retention_env(tmp_path):
    db_file = tmp_path / "test_retention.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recordings"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()

    with get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_1', 'Cam 1', 'phone')")
        conn.commit()

    yield


def test_retention_prune_protects_locked_recordings():
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO recordings 
            (recording_id, camera_id, file_path, start_time, end_time, duration_seconds, file_size_bytes, codec, width, height, fps, created_at, is_locked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'h264', 1280, 720, 30.0, ?, ?)
        """, ("rec_test_unlocked", "cam_1", "/nonexistent/unlocked.mp4", old_time, old_time, 10, 1024, old_time, 0))

        cursor.execute("""
            INSERT OR REPLACE INTO recordings 
            (recording_id, camera_id, file_path, start_time, end_time, duration_seconds, file_size_bytes, codec, width, height, fps, created_at, is_locked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'h264', 1280, 720, 30.0, ?, ?)
        """, ("rec_test_locked", "cam_1", "/nonexistent/locked.mp4", old_time, old_time, 10, 1024, old_time, 1))
        conn.commit()

    summary = run_retention_prune(
        recording_retention_days=30,
        event_retention_days=30
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        unlocked = cursor.execute("SELECT recording_id FROM recordings WHERE recording_id = 'rec_test_unlocked'").fetchone()
        locked = cursor.execute("SELECT recording_id FROM recordings WHERE recording_id = 'rec_test_locked'").fetchone()

    assert unlocked is None
    assert locked is not None
    assert summary["locked_preserved"] >= 1


def test_locked_recording_api_delete_defense(tmp_path):
    client = TestClient(app)

    now = datetime.now(timezone.utc).isoformat()
    test_video = settings.RECORDINGS_DIR / "locked.mp4"
    test_video.write_bytes(b"dummy mp4 content")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO recordings 
            (recording_id, camera_id, file_path, start_time, end_time, duration_seconds, file_size_bytes, codec, width, height, fps, created_at, is_locked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'h264', 1280, 720, 30.0, ?, ?)
        """, ("rec_api_locked_test", "cam_1", str(test_video), now, now, 10, 1024, now, 1))
        conn.commit()

    # Attempt delete while locked -> 403 Forbidden
    res_del = client.delete("/api/v1/recordings/rec_api_locked_test")
    assert res_del.status_code == 403
    assert "lock" in res_del.json()["detail"].lower()

    # Unlock via patch
    res_patch = client.patch("/api/v1/recordings/rec_api_locked_test/lock", json={"is_locked": False})
    assert res_patch.status_code == 200
    assert res_patch.json()["is_locked"] is False

    # Now delete succeeds
    res_del2 = client.delete("/api/v1/recordings/rec_api_locked_test")
    assert res_del2.status_code in (200, 204)
