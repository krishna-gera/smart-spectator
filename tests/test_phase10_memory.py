"""
Phase 10 Tests — Local Event Memory & History Analysis
Conforms to Sections 6, 7 & 37 of Phase 10 Specification.
Validates:
1. Deterministic database history queries (counts, rankings, time-of-day queries).
2. Daily activity aggregations.
3. Memory REST APIs (/api/v1/memory/*).
"""

from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
import pytest

from services.event_engine.memory import local_memory
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db
from services.hub_backend.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_memory.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_local_memory_historical_queries():
    base_time = datetime(2026, 9, 30, 23, 15, 0, tzinfo=timezone.utc)

    # Insert events into test database
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_front', 'Front Cam', 'phone')")
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_back', 'Back Cam', 'phone')")
        conn.execute(
            """
            INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
            VALUES
            ('ev_m1', 'cam_front', 'person_entered', 'medium', 'MEDIUM', 0.9, 's1', ?),
            ('ev_m2', 'cam_front', 'person_entered', 'high', 'HIGH', 0.92, 's2', ?),
            ('ev_m3', 'cam_back', 'motion_detected', 'low', 'LOW', 0.7, 's3', ?)
            """,
            (
                base_time.isoformat(),
                (base_time + timedelta(minutes=5)).isoformat(),
                (base_time - timedelta(hours=5)).isoformat(),  # 18:15:00
            ),
        )
        conn.commit()

    # 1. Count person entries
    cnt = local_memory.get_events_count(event_type="person_entered")
    assert cnt == 2

    # 2. Top cameras
    top = local_memory.get_top_cameras_by_activity(limit=2)
    assert len(top) == 2
    assert top[0]["camera_id"] == "cam_front"
    assert top[0]["event_count"] == 2

    # 3. Events occurring between 22:00 and 06:00
    night_events = local_memory.get_events_in_hour_window(start_hour=22, end_hour=6)
    assert len(night_events) == 2  # ev_m1 and ev_m2 were at 23:xx

    # 4. Daily summary
    daily = local_memory.get_daily_activity_summary(days=2)
    assert len(daily) >= 1
    assert daily[0]["total"] == 3


def test_memory_api_endpoints():
    client = TestClient(app)

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_yard', 'Yard Cam', 'phone')")
        conn.execute(
            """
            INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
            VALUES ('ev_api_1', 'cam_yard', 'loitering_detected', 'high', 'HIGH', 0.88, 'loiter', ?)
            """,
            (now_iso,),
        )
        conn.commit()

    # Test /api/v1/memory/daily-summary
    res1 = client.get("/api/v1/memory/daily-summary?days=7")
    assert res1.status_code == 200
    assert isinstance(res1.json(), list)

    # Test /api/v1/memory/top-cameras
    res2 = client.get("/api/v1/memory/top-cameras?limit=5")
    assert res2.status_code == 200
    assert any(c["camera_id"] == "cam_yard" for c in res2.json())
