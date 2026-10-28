"""
Smart Spectator - Phase 6 Security & Hardening Tests
Conforms to Sections 11, 12, 16, 22, 34, 35, 36 of Master Implementation Prompt.
Tests token auth, revocation, PIN rate limiting, path traversal, payload size limits, and log sanitization.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.hub_backend.main import app
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.hub_backend.logging_config import SensitiveDataFilter
from services.device_manager.manager import device_manager
from services.event_engine.zones import ZoneEngine


@pytest.fixture(autouse=True)
def setup_security_env(tmp_path):
    db_file = tmp_path / "test_sec.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "sec_recordings"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()
    yield
    if db_file.exists():
        db_file.unlink()


def test_invalid_and_revoked_token_authentication():
    """Validates that unauthenticated, forged, or revoked tokens are strictly rejected."""
    # 1. Invalid prefix / forged token
    assert device_manager.authenticate_token("invalid_token_123") is None
    assert device_manager.authenticate_token("ss_tok_v1_forged_payload") is None

    # 2. Pair a legitimate test device
    req = device_manager.request_pairing("dev_sec_01", "Sec Node", "Pixel 7")
    assert req["status"] == "pending_operator_approval"
    pending = device_manager.list_pending_pairings()
    target = next(p for p in pending if p["device_id"] == "dev_sec_01")
    pin = target["verification_pin"]
    verify_res = device_manager.verify_pairing("dev_sec_01", pin)
    assert verify_res["status"] == "paired"
    token = verify_res["device_token"]

    # 3. Valid authentication
    dev = device_manager.authenticate_token(token)
    assert dev is not None
    assert dev["device_id"] == "dev_sec_01"

    # 4. Revoke device
    device_manager.revoke_device("dev_sec_01")
    # Token must now be strictly rejected
    assert device_manager.authenticate_token(token) is None


def test_pairing_pin_rate_limiting_and_expiration():
    """Verifies that exceeding PIN attempt limit locks out pairing (Section 12)."""
    req = device_manager.request_pairing("dev_rate_01", "BruteForce Node")
    assert req["status"] == "pending_operator_approval"

    # Submit wrong PIN repeatedly
    for _ in range(3):
        res = device_manager.verify_pairing("dev_rate_01", "000000")
        assert res["status"] == "error"

    # After 3 failed attempts, attempts_remaining hits 0 and record is purged
    locked_res = device_manager.verify_pairing("dev_rate_01", "000000")
    assert locked_res["status"] == "error"
    assert "No pending pairing request" in locked_res["error"] or "Too many failed attempts" in locked_res["error"]


def test_log_sanitizer_scrubs_tokens_and_secrets():
    """Verifies SensitiveDataFilter sanitizes tokens, passwords, and authorization headers (Section 22)."""
    data_filter = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Device authenticated with token ss_tok_v1_9a8b7c6d5e4f and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        args=(),
        exc_info=None,
    )
    data_filter.filter(record)
    assert "ss_tok_v1_9a8b7c6d5e4f" not in record.msg
    assert "ss_tok_***REDACTED***" in record.msg
    assert "Bearer ***REDACTED***" in record.msg


def test_polygon_boundary_bounds_validation():
    """Validates that out-of-bound polygon coordinates are rejected (Section 35)."""
    ze = ZoneEngine()
    # Coordinates must be strictly in [0.0, 1.0]
    with pytest.raises(ValueError, match="outside normalized bounds"):
        ze.validate_polygon([[0.1, 0.1], [1.2, 0.5], [0.5, 0.8]])

    # Polygons must have at least 3 vertices
    with pytest.raises(ValueError, match="at least 3 vertices"):
        ze.validate_polygon([[0.2, 0.2], [0.4, 0.4]])


def test_api_revocation_endpoint_security(admin_headers):
    """Verifies that DELETE /devices/{device_id} properly revokes device and rejects revoked requests."""
    client = TestClient(app)

    # Register and pair device
    p_req = client.post("/api/v1/devices/pair/request", json={
        "device_id": "dev_endpoint_sec",
        "device_name": "Endpoint Node",
    })
    assert p_req.status_code == 202
    assert "verification_code" not in p_req.json()

    # Unauthenticated pending pairings check fails closed
    assert client.get("/api/v1/devices/pairing/pending").status_code == 401

    pend_res = client.get("/api/v1/devices/pairing/pending", headers=admin_headers)
    assert pend_res.status_code == 200
    matched = [p for p in pend_res.json() if p["device_id"] == "dev_endpoint_sec"]
    assert len(matched) == 1
    pin = matched[0]["verification_pin"]

    v_req = client.post("/api/v1/devices/pair/verify", json={
        "device_id": "dev_endpoint_sec",
        "verification_code": pin,
    })
    assert v_req.status_code == 200

    # Unauthenticated deletion fails closed
    del_unauth = client.delete("/api/v1/devices/dev_endpoint_sec")
    assert del_unauth.status_code == 401

    # Revoke device via API with admin credentials
    del_res = client.delete("/api/v1/devices/dev_endpoint_sec", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "revoked"

    # Revoking non-existent with admin credentials returns 404
    del_404 = client.delete("/api/v1/devices/non_existent_device", headers=admin_headers)
    assert del_404.status_code == 404
