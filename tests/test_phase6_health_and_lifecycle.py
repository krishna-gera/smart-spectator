"""
Smart Spectator - Phase 6 Health Probes, Hardware Identification & Crash Recovery Tests
Conforms to Sections 24, 25, 46 of Phase 6 Master Specification.
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.hub_backend.main import app
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session


@pytest.fixture
def health_test_env(tmp_path):
    db_file = tmp_path / "test_health.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "health_recs"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()
    yield
    if db_file.exists():
        db_file.unlink()


def test_shallow_and_detailed_health_endpoints(health_test_env):
    """Tests GET /api/v1/health and GET /api/v1/health/detailed (Section 24)."""
    client = TestClient(app)

    # 1. Shallow liveness check
    shallow_res = client.get("/api/v1/health")
    assert shallow_res.status_code == 200
    shallow_data = shallow_res.json()
    assert shallow_data["status"] == "healthy"
    assert "uptime_seconds" in shallow_data
    assert "version" in shallow_data

    # 2. Detailed component health check
    detailed_res = client.get("/api/v1/health/detailed")
    assert detailed_res.status_code == 200
    detailed_data = detailed_res.json()
    assert detailed_data["status"] in ("healthy", "degraded")
    assert "components" in detailed_data

    components = detailed_data["components"]
    assert "database" in components and components["database"]["status"] == "healthy"
    assert "stream_engine" in components and components["stream_engine"]["status"] == "healthy"
    assert "ai_engine" in components
    assert "event_engine" in components
    assert "recorder" in components
    assert "websocket" in components
    assert "device_manager" in components


def test_hardware_identification_endpoint(health_test_env):
    """Tests GET /api/v1/system/hardware reporting real platform hardware (Section 46)."""
    client = TestClient(app)

    res = client.get("/api/v1/system/hardware")
    assert res.status_code == 200
    data = res.json()

    assert "os" in data
    assert "architecture" in data
    assert "processor" in data
    assert "ram_total_gb" in data and data["ram_total_gb"] > 0
    assert "cpu_logical_cores" in data and data["cpu_logical_cores"] > 0
    assert "npu" in data
    assert "status" in data["npu"]
    assert "gpu_acceleration" in data
    assert "available_execution_providers" in data


def test_crash_recovery_preserves_state(health_test_env, tmp_path):
    """
    Verifies that simulating a Hub process crash and restart preserves all
    database records, rules, zones, and history without data loss (Section 25).
    """
    # 1. Populate state before crash
    with db_session() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status) VALUES ('cam_crash_01', 'Crash Cam', 'phone', 'streaming')"
        )
        conn.execute(
            """
            INSERT INTO zones (zone_id, camera_id, name, polygon_json)
            VALUES ('zone_crash_01', 'cam_crash_01', 'Perimeter', '[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8]]')
            """
        )
        conn.execute(
            """
            INSERT INTO event_rules (rule_id, name, enabled, conditions_json, actions_json)
            VALUES ('rule_crash_01', 'Intrusion Rule', 1, '{"event_type": "PERSON_ENTERED"}', '["CREATE_EVENT"]')
            """
        )
        conn.execute(
            """
            INSERT INTO events (event_id, camera_id, event_type, status, severity, confidence, summary)
            VALUES ('ev_crash_01', 'cam_crash_01', 'PERSON_ENTERED', 'confirmed', 'medium', 0.85, 'Pre-crash event')
            """
        )

    # 2. Simulate complete Hub restart by re-initializing database and checking persistence
    init_database()

    with db_session() as conn:
        cam_row = conn.execute("SELECT * FROM cameras WHERE camera_id = 'cam_crash_01'").fetchone()
        assert cam_row is not None

        zone_row = conn.execute("SELECT * FROM zones WHERE zone_id = 'zone_crash_01'").fetchone()
        assert zone_row is not None

        rule_row = conn.execute("SELECT * FROM event_rules WHERE rule_id = 'rule_crash_01'").fetchone()
        assert rule_row is not None

        ev_row = conn.execute("SELECT * FROM events WHERE event_id = 'ev_crash_01'").fetchone()
        assert ev_row is not None
        assert ev_row["status"] == "confirmed"
