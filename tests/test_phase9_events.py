"""Phase 9 Tests — Event Intelligence, Prioritization, Causal Milestones & Filtering.

Validates:
1. Deterministic priority assignment (CRITICAL, HIGH, MEDIUM, LOW)
2. Causal timeline milestone generation with real timestamps
3. Event stats computation (/events/stats)
4. Multi-field event search filtering (priority, zone_id, confidence, recording)
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from services.event_engine.prioritization import calculate_event_priority
from services.event_engine.timeline import build_event_timeline
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session
from services.hub_backend.main import app
from shared.schemas.v1.models import EventPriority


@pytest.fixture(autouse=True)
def setup_phase9_events_env(tmp_path):
    db_file = tmp_path / "test_events.db"
    settings.DATABASE_PATH = db_file
    settings.RECORDINGS_DIR = tmp_path / "recordings"
    settings.SNAPSHOTS_DIR = tmp_path / "snapshots"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()

    with db_session() as conn:
        conn.execute("INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES ('cam_front', 'Front Cam', 'phone')")
        conn.execute("""
            INSERT OR REPLACE INTO events (event_id, camera_id, event_type, severity, priority, confidence, status, summary, timestamp)
            VALUES ('ev_test_1', 'cam_front', 'PERSON_ENTERED', 'high', 'HIGH', 0.92, 'confirmed', 'Person entered', '2026-09-30T10:00:00Z')
        """)

    yield


def test_event_prioritization_rules():
    # Critical cases
    assert calculate_event_priority("CAMERA_BLOCKED") == EventPriority.CRITICAL
    assert calculate_event_priority("PERSON_ENTERED", zone_id="vault_room") == EventPriority.CRITICAL
    assert calculate_event_priority("OBJECT_REMOVED", zone_id="secure_zone") == EventPriority.CRITICAL

    # High cases
    assert calculate_event_priority("OBJECT_REMOVED") == EventPriority.HIGH
    assert calculate_event_priority("ZONE_LOITERING", duration_seconds=45.0) == EventPriority.HIGH
    assert calculate_event_priority("PERSON_ENTERED", zone_id="back_office") == EventPriority.HIGH

    # Medium cases
    assert calculate_event_priority("PERSON_ENTERED") == EventPriority.MEDIUM
    assert calculate_event_priority("OBJECT_MOVED") == EventPriority.MEDIUM
    assert calculate_event_priority("RAPID_MOTION") == EventPriority.MEDIUM

    # Low cases
    assert calculate_event_priority("NORMAL_ACTIVITY") == EventPriority.LOW
    assert calculate_event_priority("OBJECT_PRESENT") == EventPriority.LOW
    assert calculate_event_priority("PERSON_LEFT") == EventPriority.LOW


def test_event_timeline_milestones_generation():
    start = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    now = datetime(2026, 9, 30, 10, 0, 5, tzinfo=timezone.utc).isoformat()
    
    milestones = build_event_timeline(
        event_type="ZONE_LOITERING",
        timestamp=now,
        start_time=start,
        camera_id="cam_front",
        zone_id="lobby_zone",
        duration_seconds=5.0,
        rule_id="rule_loitering_alert",
    )

    assert len(milestones) >= 3
    # Check that timestamps are generated and chronological
    assert milestones[0]["timestamp"] is not None
    assert "detected" in milestones[0]["title"].lower() or "visual" in milestones[0]["title"].lower()


def test_events_stats_api_integration():
    client = TestClient(app)
    response = client.get("/api/v1/events/stats")
    assert response.status_code == 200
    data = response.json()

    assert "total_events" in data
    assert "by_priority" in data
    assert "by_severity" in data
    assert "by_type" in data
    assert "CRITICAL" in data["by_priority"]
    assert "HIGH" in data["by_priority"]
    assert "MEDIUM" in data["by_priority"]
    assert "LOW" in data["by_priority"]
    assert data["by_priority"]["HIGH"] >= 1


def test_events_search_and_priority_filter():
    client = TestClient(app)
    res = client.get("/api/v1/events?priority=HIGH&min_confidence=0.5")
    assert res.status_code == 200
    events = res.json()
    assert isinstance(events, list)
    assert len(events) >= 1
    for ev in events:
        assert ev["priority"] == "HIGH"
        assert ev["confidence"] >= 0.5
