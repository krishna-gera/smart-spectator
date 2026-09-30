"""
Phase 10 Tests — Incident Engine & Lifecycle API
Conforms to Sections 4, 31 & 37 of Phase 10 Specification.
Validates:
1. Deterministic assembly of Event + Context -> Incident (e.g. AFTER_HOURS_ENTRY).
2. Incident state transitions: OPEN -> ACKNOWLEDGED -> RESOLVED.
3. Incident REST API endpoints (/api/v1/incidents).
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest

from services.event_engine.incident_engine import (
    incident_engine,
    IncidentSeverity,
    IncidentStatus,
)
from services.event_engine.context_engine import EnvironmentalContext
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_incidents.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_after_hours_incident_generation_and_resolution():
    # Construct an after-hours context (hour 23 = 11 PM)
    ctx = EnvironmentalContext(
        timestamp=datetime.now(timezone.utc).isoformat(),
        hour_of_day=23,
        day_of_week=2,
        is_weekend=False,
        is_after_hours=True,
        camera_id="cam_server_room",
        zone_id="restricted_zone",
        zone_name="Server Vault",
        zone_type="exclusion",
    )

    ev = {
        "event_id": "ev_vault_01",
        "event_type": "person_entered",
        "priority": "CRITICAL",
        "camera_id": "cam_server_room",
        "zone_id": "restricted_zone",
        "zone_type": "exclusion",
    }

    # Evaluate incident
    inc = incident_engine.evaluate_incident(event=ev, context=ctx, persist=True)
    assert inc is not None
    assert inc.incident_type == "AFTER_HOURS_ENTRY"
    assert inc.severity == IncidentSeverity.CRITICAL
    assert inc.status == IncidentStatus.OPEN
    assert "cam_server_room" in inc.camera_ids

    # Test acknowledgement
    ack_inc = incident_engine.acknowledge_incident(inc.incident_id, operator_id="admin_1")
    assert ack_inc.status == IncidentStatus.ACKNOWLEDGED
    assert ack_inc.acknowledged_by == "admin_1"

    # Test resolution
    res_inc = incident_engine.resolve_incident(
        inc.incident_id,
        operator_id="admin_1",
        notes="Authorized night maintenance verified."
    )
    assert res_inc.status == IncidentStatus.RESOLVED
    assert res_inc.resolution_notes == "Authorized night maintenance verified."


def test_incidents_api_endpoints():
    client = TestClient(app)

    # 1. Create incident via engine
    ctx = EnvironmentalContext(
        timestamp=datetime.now(timezone.utc).isoformat(),
        hour_of_day=2,
        day_of_week=6,
        is_weekend=True,
        is_after_hours=True,
        camera_id="cam_dock",
    )
    ev = {
        "event_id": "ev_dock_99",
        "event_type": "person_entered",
        "priority": "HIGH",
        "camera_id": "cam_dock",
    }
    inc = incident_engine.evaluate_incident(event=ev, context=ctx, persist=True)

    # 2. Query /api/v1/incidents
    res = client.get("/api/v1/incidents")
    assert res.status_code == 200
    incidents = res.json()
    assert len(incidents) >= 1
    assert any(i["incident_id"] == inc.incident_id for i in incidents)

    # 3. Acknowledge via API
    ack_res = client.post(
        f"/api/v1/incidents/{inc.incident_id}/acknowledge",
        json={"operator_id": "sec_operator_42"}
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # 4. Resolve via API
    res_res = client.post(
        f"/api/v1/incidents/{inc.incident_id}/resolve",
        json={"operator_id": "sec_operator_42", "resolution_notes": "False alarm confirmed."}
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
    assert res_res.json()["resolution_notes"] == "False alarm confirmed."
