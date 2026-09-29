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
    
    # Step 1: Request pairing
    req_res = device_manager.request_pairing(
        device_id=device_id,
        device_name=device_name,
        device_model="Pixel 7 Pro",
        ip_address="192.168.1.45"
    )
    assert req_res["status"] == "pending_operator_approval"
    pin = req_res["verification_code"]
    assert len(pin) == 6

    # Step 2: Verify pairing with correct PIN
    ver_res = device_manager.verify_pairing(device_id=device_id, submitted_pin=pin)
    assert ver_res["status"] == "paired"
    assert "device_token" in ver_res
    assert ver_res["token_type"] == "Bearer"
    token = ver_res["device_token"]
    
    # Step 3: Authenticate token
    authenticated_device = device_manager.authenticate_token(token)
    assert authenticated_device is not None
    assert authenticated_device["device_id"] == device_id
    assert authenticated_device["device_name"] == device_name
    assert authenticated_device["status"] == "paired"


def test_pairing_invalid_pin_decrements_attempts():
    device_id = "dev_android_bad_pin"
    req_res = device_manager.request_pairing(
        device_id=device_id,
        device_name="Attacker Phone"
    )
    
    # Submit incorrect PIN
    bad_res = device_manager.verify_pairing(device_id=device_id, submitted_pin="000000")
    assert bad_res["status"] == "error"
    assert "Invalid verification code" in bad_res["error"]
    
    # Check attempts remaining
    with db_session() as conn:
        row = conn.execute("SELECT attempts_remaining FROM pairing_requests WHERE device_id = ?", (device_id,)).fetchone()
        assert row["attempts_remaining"] == 2


def test_device_revocation():
    device_id = "dev_to_revoke"
    req = device_manager.request_pairing(device_id, "Temporary Device")
    ver = device_manager.verify_pairing(device_id, req["verification_code"])
    token = ver["device_token"]
    
    # Authenticate before revocation
    assert device_manager.authenticate_token(token) is not None
    
    # Revoke device
    revoked = device_manager.revoke_device(device_id)
    assert revoked is True
    
    # Attempt authentication after revocation (must fail)
    assert device_manager.authenticate_token(token) is None
