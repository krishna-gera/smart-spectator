"""
Smart Spectator - Phase 4 & Phase 5 REST API & Client Endpoint Tests
Tests events, zones, rules, recordings, metrics, audit, and client dashboard serving.
Conforms to Sections 19, 20, 21, 22, 67, 72 of Phase 4 & 5 specifications.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.hub_backend.main import app
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.event_engine import event_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_api_env(tmp_path):
    db_file = tmp_path / "test_api_full.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recordings"
    settings.SNAPSHOTS_DIR = tmp_path / "snapshots"
    init_database()

    # Prepopulate a test camera
    with db_session() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO cameras (camera_id, name, source_type, width, height, target_fps)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("cam_api_01", "Front Door Cam", "phone", 1280, 720, 30),
        )

    yield
    if db_file.exists():
        os.remove(db_file)


def test_zone_crud_apis():
    # 1. Create Zone
    zone_data = {
        "name": "Porch Area",
        "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
        "color": "#38bdf8",
        "is_active": True,
    }
    create_res = client.post("/api/v1/cameras/cam_api_01/zones", json=zone_data)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["name"] == "Porch Area"
    assert created["zone_id"].startswith("zone_")
    zone_id = created["zone_id"]

    # 2. List Zones for camera
    list_res = client.get("/api/v1/cameras/cam_api_01/zones")
    assert list_res.status_code == 200
    zones = list_res.json()
    assert any(z["zone_id"] == zone_id for z in zones)

    # 3. Update Zone
    update_res = client.put(f"/api/v1/zones/{zone_id}", json={"name": "Updated Porch Area"})
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Updated Porch Area"

    # 4. Delete Zone
    del_res = client.delete(f"/api/v1/zones/{zone_id}")
    assert del_res.status_code == 204

    # Verify deleted
    list_after = client.get("/api/v1/cameras/cam_api_01/zones").json()
    assert not any(z["zone_id"] == zone_id for z in list_after)


def test_rule_crud_and_toggle_apis():
    # 1. Create Rule
    rule_data = {
        "name": "Night Entry Alert",
        "enabled": True,
        "conditions": {
            "event_type": "PERSON_ENTERED",
            "camera_id": "cam_api_01",
            "minimum_confidence": 0.80,
        },
        "actions": ["CREATE_EVENT", "SAVE_CLIP"],
        "cooldown_seconds": 45,
    }
    create_res = client.post("/api/v1/rules", json=rule_data)
    assert create_res.status_code == 201
    rule = create_res.json()
    assert rule["name"] == "Night Entry Alert"
    rule_id = rule["rule_id"]

    # 2. Get Rules
    list_res = client.get("/api/v1/rules")
    assert list_res.status_code == 200
    assert any(r["rule_id"] == rule_id for r in list_res.json())

    # 3. Disable Rule
    dis_res = client.post(f"/api/v1/rules/{rule_id}/disable")
    assert dis_res.status_code == 200
    assert dis_res.json()["enabled"] is False

    # 4. Enable Rule
    en_res = client.post(f"/api/v1/rules/{rule_id}/enable")
    assert en_res.status_code == 200
    assert en_res.json()["enabled"] is True

    # 5. Delete Rule
    del_res = client.delete(f"/api/v1/rules/{rule_id}")
    assert del_res.status_code == 204


def test_events_query_and_lifecycle_apis():
    # Insert dummy event into SQLite
    ev_id = "ev_api_test_01"
    now_str = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO events (
                event_id, camera_id, event_type, status, severity,
                confidence, summary, timestamp, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ev_id, "cam_api_01", "PERSON_ENTERED", "confirmed", "high", 0.92, "Person entered front door", now_str, now_str, now_str),
        )

    # 1. List Events
    res = client.get("/api/v1/events", params={"camera_id": "cam_api_01", "severity": "high"})
    assert res.status_code == 200
    events = res.json()
    assert any(e["event_id"] == ev_id for e in events)

    # 2. Get Single Event
    ev_res = client.get(f"/api/v1/events/{ev_id}")
    assert ev_res.status_code == 200
    assert ev_res.json()["event_id"] == ev_id

    # 3. Acknowledge Event
    ack_res = client.post(f"/api/v1/events/{ev_id}/acknowledge")
    assert ack_res.status_code == 200
    assert ack_res.json()["metadata"]["acknowledged"] is True

    # 4. Resolve Event
    res_res = client.post(f"/api/v1/events/{ev_id}/resolve")
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "resolved"


def test_system_telemetry_and_audit_apis():
    # 1. System Metrics
    m_res = client.get("/api/v1/system/metrics")
    assert m_res.status_code == 200
    m_data = m_res.json()
    assert "event_engine" in m_data
    assert "ai_pipeline" in m_data
    assert "storage" in m_data

    # 2. Decoupled Component Health
    h_res = client.get("/api/v1/system/health/components")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert "components" in h_data
    assert h_data["components"]["database"] == "healthy"

    # 3. Audit Logs
    a_res = client.get("/api/v1/system/audit")
    assert a_res.status_code == 200
    assert isinstance(a_res.json(), list)


def test_client_dashboard_serving():
    """Verify Phase 5 Client index.html is served at root GET / (Section 34)."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Smart Spectator" in res.text
    assert "main-content" in res.text
