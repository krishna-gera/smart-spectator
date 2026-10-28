"""
Unit & Integration Tests for Device Pairing and HMAC Authentication
Tests SS-DOC-006 and SS-DOC-013 compliance
"""

import pytest
import os
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.device_manager.credentials import (
    generate_pairing_pin,
    generate_device_token,
    verify_device_token
)
from services.device_manager.manager import device_manager


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Sets up an isolated SQLite test database for each test run."""
    db_file = tmp_path / "test_spectator.db"
    settings.DATABASE_PATH = db_file
    init_database()
    yield
    if db_file.exists():
        os.remove(db_file)


def test_pin_generation():
    pin = generate_pairing_pin()
    assert len(pin) == 6
    assert pin.isdigit()
    assert 100000 <= int(pin) <= 999999


def test_device_token_hmac_verification():
    raw_token, token_hash = generate_device_token("dev_test_123")
    assert raw_token.startswith("ss_tok_v1_")
    assert len(token_hash) == 64 # SHA-256 hex digest
    
    # Constant-time verification
    assert verify_device_token(raw_token, token_hash) is True
    assert verify_device_token("ss_tok_v1_wrongsecret", token_hash) is False
    assert verify_device_token("", token_hash) is False


def test_pairing_workflow_success():
    device_id = "dev_android_test_01"
    device_name = "Pixel 7 Test"
    
    # Step 1: Request pairing (PIN must NEVER be returned to the client)
    req_res = device_manager.request_pairing(
        device_id=device_id,
        device_name=device_name,
        device_model="Pixel 7 Pro",
        ip_address="192.168.1.45"
    )
    assert req_res["status"] == "pending_operator_approval"
    assert "verification_code" not in req_res
    assert req_res["expires_in_seconds"] == settings.PAIRING_PIN_TTL_SECONDS

    # Step 2: Hub operator views pending pairing requests to obtain PIN
    pending = device_manager.list_pending_pairings()
    assert len(pending) >= 1
    target = next((p for p in pending if p["device_id"] == device_id), None)
    assert target is not None
    pin = target["verification_pin"]
    assert len(pin) == 6
    assert pin.isdigit()

    # Step 3: Verify pairing with correct PIN
    ver_res = device_manager.verify_pairing(device_id=device_id, submitted_pin=pin)
    assert ver_res["status"] == "paired"
    assert "device_token" in ver_res
    assert ver_res["token_type"] == "Bearer"
    token = ver_res["device_token"]
    
    # Step 4: Authenticate token
    authenticated_device = device_manager.authenticate_token(token)
    assert authenticated_device is not None
    assert authenticated_device["device_id"] == device_id
    assert authenticated_device["device_name"] == device_name
    assert authenticated_device["status"] == "paired"


def test_pairing_invalid_pin_decrements_attempts_and_locks():
    device_id = "dev_android_bad_pin"
    req_res = device_manager.request_pairing(
        device_id=device_id,
        device_name="Attacker Phone"
    )
    assert "verification_code" not in req_res
    
    # Submit incorrect PIN (attempt 1)
    bad_res1 = device_manager.verify_pairing(device_id=device_id, submitted_pin="000000")
    assert bad_res1["status"] == "error"
    assert "2 attempt(s) remaining" in bad_res1["error"]
    
    # Check attempts remaining
    with db_session() as conn:
        row = conn.execute("SELECT attempts_remaining FROM pairing_requests WHERE device_id = ?", (device_id,)).fetchone()
        assert row["attempts_remaining"] == 2

    # Submit incorrect PIN (attempt 2)
    bad_res2 = device_manager.verify_pairing(device_id=device_id, submitted_pin="000000")
    assert bad_res2["status"] == "error"
    assert "1 attempt(s) remaining" in bad_res2["error"]

    # Submit incorrect PIN (attempt 3 - lockout)
    bad_res3 = device_manager.verify_pairing(device_id=device_id, submitted_pin="000000")
    assert bad_res3["status"] == "error"
    assert "Too many failed attempts" in bad_res3["error"]

    # Ephemeral pairing record should now be deleted
    with db_session() as conn:
        row = conn.execute("SELECT * FROM pairing_requests WHERE device_id = ?", (device_id,)).fetchone()
        assert row is None


def test_device_revocation():
    device_id = "dev_to_revoke"
    device_manager.request_pairing(device_id, "Temporary Device")
    pending = device_manager.list_pending_pairings()
    target = next(p for p in pending if p["device_id"] == device_id)
    ver = device_manager.verify_pairing(device_id, target["verification_pin"])
    token = ver["device_token"]
    
    # Authenticate before revocation
    assert device_manager.authenticate_token(token) is not None
    
    # Revoke device
    revoked = device_manager.revoke_device(device_id)
    assert revoked is True
    
    # Attempt authentication after revocation (must fail)
    assert device_manager.authenticate_token(token) is None


def test_pairing_expired_pin_rejected():
    device_id = "dev_expired_pin"
    device_manager.request_pairing(device_id, "Expired Device")
    
    # Manually backdate expiration in SQLite
    with db_session() as conn:
        conn.execute(
            "UPDATE pairing_requests SET expires_at = '2020-01-01T00:00:00+00:00' WHERE device_id = ?",
            (device_id,)
        )
        
    res = device_manager.verify_pairing(device_id, "123456")
    assert res["status"] == "error"
    assert "expired" in res["error"].lower()
    
    # Record should have been cleaned up
    with db_session() as conn:
        row = conn.execute("SELECT * FROM pairing_requests WHERE device_id = ?", (device_id,)).fetchone()
        assert row is None
