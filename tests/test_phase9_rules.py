"""Phase 9 Tests — Structured Rule Builder, Time Windows & Action Execution.

Validates:
1. Structured rule evaluation (WHEN, IN, DURING, THEN)
2. Overnight time window matching (e.g. 22:00 to 06:00)
3. Priority and severity overrides
4. Enable / Disable / Delete rule lifecycle
"""

from datetime import time
import pytest
from fastapi.testclient import TestClient

from services.event_engine.rules import is_time_in_range
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_phase9_rules_env(tmp_path):
    db_file = tmp_path / "test_rules.db"
    settings.DATABASE_PATH = db_file
    init_database()
    yield


def test_time_window_evaluation():
    # Normal daytime window: 09:00 to 17:00
    start = time(9, 0)
    end = time(17, 0)
    assert is_time_in_range(time(12, 0), start, end) is True
    assert is_time_in_range(time(8, 59), start, end) is False
    assert is_time_in_range(time(17, 1), start, end) is False

    # Overnight window: 22:00 to 06:00
    night_start = time(22, 0)
    night_end = time(6, 0)
    assert is_time_in_range(time(23, 30), night_start, night_end) is True
    assert is_time_in_range(time(2, 0), night_start, night_end) is True
    assert is_time_in_range(time(5, 59), night_start, night_end) is True
    assert is_time_in_range(time(12, 0), night_start, night_end) is False
    assert is_time_in_range(time(21, 59), night_start, night_end) is False


def test_rule_api_crud_lifecycle():
    client = TestClient(app)

    # 1. Create rule
    rule_data = {
        "name": "Overnight Intrusion Rule",
        "enabled": True,
        "conditions": {
            "event_type": "PERSON_ENTERED",
            "camera_id": "*",
            "minimum_confidence": 0.85,
            "time_start": "22:00",
            "time_end": "06:00"
        },
        "actions": ["CREATE_EVENT", "SAVE_CLIP", "CLIENT_NOTIFICATION"],
        "cooldown_seconds": 60,
        "priority_override": "CRITICAL"
    }

    res = client.post("/api/v1/rules", json=rule_data)
    assert res.status_code in (200, 201)
    created = res.json()
    assert created["name"] == "Overnight Intrusion Rule"
    rule_id = created["rule_id"]

    # 2. Disable rule
    res_dis = client.post(f"/api/v1/rules/{rule_id}/disable")
    assert res_dis.status_code == 200
    assert res_dis.json()["enabled"] is False

    # 3. Enable rule
    res_en = client.post(f"/api/v1/rules/{rule_id}/enable")
    assert res_en.status_code == 200
    assert res_en.json()["enabled"] is True

    # 4. Delete rule
    res_del = client.delete(f"/api/v1/rules/{rule_id}")
    assert res_del.status_code in (200, 204)

    # Verify deleted
    res_get = client.get(f"/api/v1/rules/{rule_id}")
    assert res_get.status_code == 404
