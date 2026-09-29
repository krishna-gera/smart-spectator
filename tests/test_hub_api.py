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


def test_pairing_api_end_to_end():
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
    pin = req_data["verification_code"]

    # 2. Check pending PINs endpoint for Desktop UI
    pending_res = client.get("/api/v1/devices/pairing/pending")
    assert pending_res.status_code == 200
    pending_pins = pending_res.json()
    assert any(p["verification_pin"] == pin for p in pending_pins)

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

    # 4. Check device listed
    devs_res = client.get("/api/v1/devices")
    assert devs_res.status_code == 200
    devs = devs_res.json()
    assert any(d["device_id"] == "dev_integration_api" for d in devs)

    # 5. Check camera created
    cams_res = client.get("/api/v1/cameras")
    assert cams_res.status_code == 200
    cams = cams_res.json()
    assert len(cams) >= 1
    assert any(c["device_id"] == "dev_integration_api" for c in cams)


def test_unauthenticated_device_revocation():
    # Non-existent device returns 404
    res = client.delete("/api/v1/devices/non_existent_id")
    assert res.status_code == 404
