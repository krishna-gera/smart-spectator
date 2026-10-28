"""
Smart Spectator - Authentication, RBAC, and Destructive Endpoint Security Tests
Validates Steps 2, 3, 4 of Engineering Remediation Plan.
"""

import pytest
import os
from fastapi.testclient import TestClient

from services.hub_backend.main import app
from services.hub_backend.config import Settings, settings
from services.hub_backend.database.connection import init_database
from services.hub_backend.auth.roles import Role
from services.hub_backend.auth.tokens import create_access_token, verify_access_token
from services.hub_backend.auth.user_manager import user_manager
from services.device_manager.manager import device_manager


@pytest.fixture(autouse=True)
def setup_test_auth_db(tmp_path):
    """Sets up an isolated SQLite test database with seeded admin."""
    db_file = tmp_path / "test_auth_spectator.db"
    settings.DATABASE_PATH = db_file
    init_database()
    user_manager.seed_default_admin()
    yield
    if db_file.exists():
        os.remove(db_file)


def test_admin_login_success_and_token_issue():
    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["token_type"] == "Bearer"

    # Verify identity with issued token
    token = data["access_token"]
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me = me_res.json()
    assert me["username"] == "admin"
    assert me["role"] == "admin"


def test_login_invalid_password_fails_closed():
    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]


def test_unauthenticated_requests_strictly_rejected():
    client = TestClient(app)
    
    # 1. Unauthenticated read
    assert client.get("/api/v1/devices").status_code == 401
    assert client.get("/api/v1/recordings").status_code == 401
    assert client.get("/api/v1/events").status_code == 401
    assert client.get("/api/v1/rules").status_code == 401

    # 2. Unauthenticated mutations
    assert client.post("/api/v1/rules", json={
        "name": "Test Rule",
        "conditions": {}
    }).status_code == 401

    # 3. Unauthenticated destructive actions
    assert client.delete("/api/v1/devices/dev_fake").status_code == 401
    assert client.delete("/api/v1/recordings/rec_fake").status_code == 401
    assert client.post("/api/v1/system/restore", json={"backup_file": "backup.db"}).status_code == 401


def test_rbac_viewer_operator_admin_privilege_ladder():
    client = TestClient(app)

    viewer_token = create_access_token("usr_viewer", "test_viewer", Role.VIEWER)
    operator_token = create_access_token("usr_operator", "test_operator", Role.OPERATOR)
    admin_token = create_access_token("usr_admin", "test_admin", Role.ADMIN)

    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. VIEWER can read devices, but CANNOT create rules or delete devices
    assert client.get("/api/v1/devices", headers=viewer_headers).status_code == 200
    assert client.post("/api/v1/rules", json={
        "name": "Viewer Rule",
        "conditions": {}
    }, headers=viewer_headers).status_code == 403
    assert client.delete("/api/v1/devices/dev_fake", headers=viewer_headers).status_code == 403

    # 2. OPERATOR can create rules and view pending pairings, but CANNOT delete devices
    create_rule_res = client.post("/api/v1/rules", json={
        "name": "Operator Rule",
        "conditions": {"category": "test"}
    }, headers=operator_headers)
    assert create_rule_res.status_code == 201
    assert client.get("/api/v1/devices/pairing/pending", headers=operator_headers).status_code == 200
    # Destructive device revocation is admin only
    assert client.delete("/api/v1/devices/dev_fake", headers=operator_headers).status_code == 403

    # 3. ADMIN can perform all operations
    assert client.get("/api/v1/devices", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/devices/pairing/pending", headers=admin_headers).status_code == 200
    # Revoking non-existent device returns 404, proving authentication passed!
    assert client.delete("/api/v1/devices/non_existent_id", headers=admin_headers).status_code == 404


def test_logout_revokes_token():
    client = TestClient(app)

    token = create_access_token("usr_revocable", "test_rev", Role.OPERATOR)
    headers = {"Authorization": f"Bearer {token}"}

    # Token works initially
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"

    # Subsequent access with same token is rejected
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_production_security_validation_fails_closed():
    # 1. Default HMAC secret in production raises ValueError
    with pytest.raises(ValueError, match="Production mode requires an explicit HUB_HMAC_SECRET"):
        Settings(
            ENVIRONMENT="production",
            HMAC_SECRET="smart-spectator-local-secret-key-change-in-prod",
            DEFAULT_ADMIN_PASSWORD="StrongProductionPassword987!"
        )

    # 2. Default admin password in production raises ValueError
    with pytest.raises(ValueError, match="Production mode requires an explicit HUB_ADMIN_PASSWORD"):
        Settings(
            ENVIRONMENT="production",
            HMAC_SECRET="a" * 32,
            DEFAULT_ADMIN_PASSWORD="admin123"
        )

    # 3. Wildcard CORS in production raises ValueError
    with pytest.raises(ValueError, match=r"Wildcard '\*' CORS origin is not permitted"):
        Settings(
            ENVIRONMENT="production",
            HMAC_SECRET="a" * 32,
            DEFAULT_ADMIN_PASSWORD="StrongProductionPassword987!",
            ALLOWED_ORIGINS=["*"]
        )

    # 4. Valid production settings succeed
    valid_prod = Settings(
        ENVIRONMENT="production",
        HMAC_SECRET="a" * 32,
        DEFAULT_ADMIN_PASSWORD="StrongProductionPassword987!",
        ALLOWED_ORIGINS=["https://spectator.local"]
    )
    assert valid_prod.is_production is True
