"""Phase 9 Tests — Extended REST APIs & Data Integrity.

Validates:
1. GET /api/v1/system/storage statistics
2. POST /api/v1/system/storage/retention/cleanup
3. GET /api/v1/system/activity operator logs
4. GET /api/v1/system/config export & import APIs
"""

import pytest
from fastapi.testclient import TestClient
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_phase9_api_env(tmp_path):
    db_file = tmp_path / "test_api.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recordings"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()
    yield


def test_storage_stats_api(viewer_headers):
    client = TestClient(app)
    assert client.get("/api/v1/system/storage").status_code == 401
    res = client.get("/api/v1/system/storage", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()

    assert "disk_total_gb" in data
    assert "disk_free_gb" in data
    assert "recordings_storage_gb" in data
    assert "database_size_mb" in data
    assert "retention_policies" in data
    assert data["disk_total_gb"] > 0


def test_retention_cleanup_api(operator_headers):
    client = TestClient(app)
    assert client.post("/api/v1/system/storage/retention/cleanup").status_code == 401
    res = client.post("/api/v1/system/storage/retention/cleanup", headers=operator_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "deleted_recordings" in data
    assert "deleted_events" in data
    assert "locked_preserved" in data


def test_operator_activity_api(viewer_headers):
    client = TestClient(app)
    assert client.get("/api/v1/system/activity?limit=5").status_code == 401
    res = client.get("/api/v1/system/activity?limit=5", headers=viewer_headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_config_export_and_import_apis(admin_headers):
    client = TestClient(app)
    assert client.get("/api/v1/system/config/export").status_code == 401

    # Export
    res_exp = client.get("/api/v1/system/config/export", headers=admin_headers)
    assert res_exp.status_code == 200
    cfg = res_exp.json()
    assert cfg["schema_version"] == "1.2.0"

    # Import fails closed without auth
    assert client.post("/api/v1/system/config/import", json=cfg).status_code == 401

    # Import
    res_imp = client.post("/api/v1/system/config/import", json=cfg, headers=admin_headers)
    assert res_imp.status_code == 200
    imp_data = res_imp.json()
    assert imp_data["status"] == "success"
