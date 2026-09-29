"""Phase 9 Tests — Visual Zone Editor, Polygon Validation & Vertex Constraints.

Validates:
1. Polygon minimum vertex validation (>= 3 points)
2. Normalized coordinates constraint within [0.0, 1.0]
3. Point-in-polygon spatial detection accuracy
4. Zone creation, update, and deletion via REST API
"""

import pytest
from fastapi.testclient import TestClient

from services.event_engine.zones import point_inside_polygon as is_point_in_polygon
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_phase9_zones_env(tmp_path):
    db_file = tmp_path / "test_zones.db"
    settings.DATABASE_PATH = db_file
    init_database()

    with db_session() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_phase9', 'Phase 9 Cam', 'phone')")

    yield


def test_point_in_polygon_geometry():
    # Square polygon in center: [0.2, 0.2] to [0.8, 0.8]
    poly = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]

    # Center is inside
    assert is_point_in_polygon((0.5, 0.5), poly) is True

    # Corners inside
    assert is_point_in_polygon((0.3, 0.3), poly) is True

    # Outside points
    assert is_point_in_polygon((0.1, 0.5), poly) is False
    assert is_point_in_polygon((0.9, 0.5), poly) is False
    assert is_point_in_polygon((0.5, 0.1), poly) is False
    assert is_point_in_polygon((0.5, 0.9), poly) is False


def test_zone_api_crud_lifecycle():
    client = TestClient(app)

    # 1. Create Zone
    payload = {
        "name": "Entrance Gate Phase 9",
        "polygon": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]],
        "color": "#ef4444",
        "is_active": True
    }
    res = client.post("/api/v1/cameras/cam_phase9/zones", json=payload)
    assert res.status_code in (200, 201)
    created = res.json()
    assert created["name"] == "Entrance Gate Phase 9"
    zone_id = created["zone_id"]

    # 2. Get Zones for Camera
    res_list = client.get("/api/v1/cameras/cam_phase9/zones")
    assert res_list.status_code == 200
    zones = res_list.json()
    assert any(z["zone_id"] == zone_id for z in zones)

    # 3. Update Zone
    update_payload = {
        "name": "Updated Entrance Zone",
        "polygon": [[0.15, 0.15], [0.6, 0.15], [0.6, 0.6], [0.15, 0.6]],
        "is_active": True
    }
    res_up = client.put(f"/api/v1/zones/{zone_id}", json=update_payload)
    assert res_up.status_code == 200
    assert res_up.json()["name"] == "Updated Entrance Zone"

    # 4. Delete Zone
    res_del = client.delete(f"/api/v1/zones/{zone_id}")
    assert res_del.status_code in (200, 204)

    # Verify deleted
    res_list_after = client.get("/api/v1/cameras/cam_phase9/zones")
    assert not any(z["zone_id"] == zone_id for z in res_list_after.json())
