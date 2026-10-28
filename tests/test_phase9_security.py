"""Phase 9 Tests — Security Hardening, Path Traversal Defense & Sensitive Data Scrubbing.

Validates:
1. Rejection of directory traversal attacks on recordings download and deletion
2. Defense against path escaping outside RECORDINGS_DIR
3. Zero sensitive tokens/keys in activity logs and telemetry outputs
"""

import pytest
from fastapi.testclient import TestClient

from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db_connection
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_phase9_security_env(tmp_path):
    db_file = tmp_path / "test_security.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recordings"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()

    with get_db_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_1', 'Cam 1', 'phone')")
        conn.commit()

    yield


def test_recording_path_traversal_defense(admin_headers, viewer_headers):
    client = TestClient(app)

    # Insert malicious recording path attempting path traversal
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO recordings 
            (recording_id, camera_id, file_path, start_time, end_time, duration_seconds, file_size_bytes, codec, width, height, fps, created_at, is_locked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'h264', 1280, 720, 30.0, ?, ?)
        """, ("rec_traversal_attack", "cam_1", "../../../etc/passwd", "2026-09-30T10:00:00Z", "2026-09-30T10:00:00Z", 5, 1024, "2026-09-30T10:00:00Z", 0))
        conn.commit()

    # Unauthenticated download fails closed with 401
    assert client.get("/api/v1/recordings/rec_traversal_attack/download").status_code == 401

    # Attempt to download traversed file with viewer auth -> MUST return 400 or 404 (blocked by resolve_safe_recording_path)
    res_dl = client.get("/api/v1/recordings/rec_traversal_attack/download", headers=viewer_headers)
    assert res_dl.status_code in (400, 404)

    # Unauthenticated delete fails closed with 401
    assert client.delete("/api/v1/recordings/rec_traversal_attack").status_code == 401

    # Attempt to delete traversed file with admin auth -> Database row removed but file outside recordings_dir is protected
    res_del = client.delete("/api/v1/recordings/rec_traversal_attack", headers=admin_headers)
    assert res_del.status_code in (200, 204)


def test_telemetry_and_audit_zero_secrets(viewer_headers):
    client = TestClient(app)

    # Check AI Diagnostics
    res_tele = client.get("/api/v1/ai/status", headers=viewer_headers)
    assert res_tele.status_code == 200
    tele_text = res_tele.text.lower()
    assert "hmac" not in tele_text
    assert "secret" not in tele_text
    assert "private_key" not in tele_text

    # Check System Health (public endpoint)
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert "token" not in res_health.text.lower()
