"""
Integration Tests for Smart Spectator Hub FastAPI Endpoints
Tests SS-DOC-007 compliance
"""

import pytest
import os
from fastapi.testclient import TestClient
from services.hub_backend.main import app
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from services.device_manager.manager import device_manager


@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path):
    db_file = tmp_path / "test_api_spectator.db"
    settings.DATABASE_PATH = db_file
    init_database()
    yield
    if db_file.exists():
        os.remove(db_file)


client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data


def test_system_status_endpoint():
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    data = res.json()
    assert "hub_ip" in data
    assert "api_port" in data
    assert "active_streaming_cameras" in data


def test_pairing_api_end_to_end(admin_headers, viewer_headers):
    # 1. Pairing Request
    req_payload = {
        "device_id": "dev_integration_api",
        "device_name": "Living Room Pixel",
        "device_model": "Pixel 7 Pro",
        "os_version": "Android 14",
        "app_version": "1.0.0"
    }
    req_res = client.post("/api/v1/devices/pair/request", json=req_payload)
    assert req_res.status_code == 202
    req_data = req_res.json()
    assert req_data["status"] == "pending_operator_approval"
    assert "verification_code" not in req_data

    # 2. Check pending PINs endpoint for Desktop UI / Operator (fails closed without auth)
    unauth_pending = client.get("/api/v1/devices/pairing/pending")
    assert unauth_pending.status_code == 401

    pending_res = client.get("/api/v1/devices/pairing/pending", headers=admin_headers)
    assert pending_res.status_code == 200
    pending_pins = pending_res.json()
    matched = [p for p in pending_pins if p["device_id"] == "dev_integration_api"]
    assert len(matched) == 1
    pin = matched[0]["verification_pin"]

    # 3. Pairing Verification
    verify_payload = {
        "device_id": "dev_integration_api",
        "verification_code": pin
    }
    verify_res = client.post("/api/v1/devices/pair/verify", json=verify_payload)
    assert verify_res.status_code == 200
    verify_data = verify_res.json()
    assert verify_data["status"] == "paired"
    token = verify_data["device_token"]
    assert token.startswith("ss_tok_v1_")

    # 4. Check device listed (requires viewer auth)
    devs_res = client.get("/api/v1/devices", headers=viewer_headers)
    assert devs_res.status_code == 200
    devs = devs_res.json()
    assert any(d["device_id"] == "dev_integration_api" for d in devs)

    # 5. Check camera created
    cams_res = client.get("/api/v1/cameras", headers=viewer_headers)
    assert cams_res.status_code == 200
    cams = cams_res.json()
    assert len(cams) >= 1
    assert any(c["device_id"] == "dev_integration_api" for c in cams)


def test_unauthenticated_device_revocation(admin_headers):
    # Unauthenticated request fails closed with 401
    res = client.delete("/api/v1/devices/non_existent_id")
    assert res.status_code == 401

    # Authenticated request for non-existent device returns 404
    res_auth = client.delete("/api/v1/devices/non_existent_id", headers=admin_headers)
    assert res_auth.status_code == 404


def test_camera_rename_and_lifecycle_apis(operator_headers):
    # 1. Setup camera record
    from services.hub_backend.database.connection import db_session
    with db_session() as conn:
        conn.execute("INSERT OR REPLACE INTO cameras (camera_id, name, source_type) VALUES ('cam_hub_test_1', 'Original Cam', 'phone')")

    # 2. Test Rename (PUT /cameras/{id})
    res = client.put("/api/v1/cameras/cam_hub_test_1", json={"name": "Renamed Cam 1"}, headers=operator_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed Cam 1"

    # 3. Test Disconnect & Reconnect
    res_disc = client.post("/api/v1/cameras/cam_hub_test_1/disconnect", headers=operator_headers)
    assert res_disc.status_code == 200
    assert res_disc.json()["status"] == "disconnected"

    res_rec = client.post("/api/v1/cameras/cam_hub_test_1/reconnect", headers=operator_headers)
    assert res_rec.status_code == 200
    assert res_rec.json()["status"] == "streaming"


def test_ai_telemetry_endpoint(viewer_headers):
    res = client.get("/api/v1/ai/telemetry", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert "active_backend" in data
    assert "camera_contexts" in data

