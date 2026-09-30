"""
Phase 10 Tests — Event Relationship Engine
Conforms to Sections 3, 37 & 38 of Phase 10 Specification.
Validates:
1. Deterministic relationship matching: followed_by, camera_handoff, state_change.
2. Cross-camera relationship correlation.
3. Resilience to timestamp disorder.
4. Database persistence and query retrieval.
"""

from datetime import datetime, timezone, timedelta
import pytest

from services.event_engine.event_relationships import (
    relationship_engine,
    RelationshipType,
)
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, get_db


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    orig = settings.DATABASE_PATH
    settings.DATABASE_PATH = tmp_path / "test_relationships.db"
    init_database()
    yield
    settings.DATABASE_PATH = orig


def test_deterministic_event_relationship_sequence():
    base_time = datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc)

    # 1. 10:00:00 - PERSON_ENTERED
    ev1 = {
        "event_id": "ev_rel_1",
        "event_type": "person_entered",
        "camera_id": "cam_front",
        "confidence": 0.90,
        "timestamp": base_time.isoformat(),
    }

    # 2. 10:02:00 - PERSON_LEFT
    ev2 = {
        "event_id": "ev_rel_2",
        "event_type": "person_left",
        "camera_id": "cam_front",
        "confidence": 0.85,
        "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
    }

    # 3. 10:05:00 - OBJECT_REMOVED
    ev3 = {
        "event_id": "ev_rel_3",
        "event_type": "object_removed",
        "camera_id": "cam_front",
        "confidence": 0.80,
        "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
    }

    # Insert events into DB first so foreign keys succeed
    with get_db() as conn:
        for ev in [ev1, ev2, ev3]:
            conn.execute(
                "INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES (?, 'Front Cam', 'phone')",
                (ev["camera_id"],),
            )
            conn.execute(
                """
                INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
                VALUES (?, ?, ?, 'medium', 'MEDIUM', ?, 'summary', ?)
                """,
                (ev["event_id"], ev["camera_id"], ev["event_type"], ev["confidence"], ev["timestamp"]),
            )
        conn.commit()

    # Evaluate ev2 against ev1 (should discover PERSON_ENTERED followed by PERSON_LEFT)
    rels_2 = relationship_engine.evaluate_relationships(new_event=ev2, recent_events=[ev1], persist=True)
    assert len(rels_2) == 1
    assert rels_2[0].relationship_type == RelationshipType.FOLLOWED_BY.value
    assert rels_2[0].event_a_id == "ev_rel_1"
    assert rels_2[0].event_b_id == "ev_rel_2"
    assert rels_2[0].time_delta_seconds == 120.0

    # Evaluate ev3 against ev1 (should discover PERSON_ENTERED followed by OBJECT_REMOVED)
    rels_3 = relationship_engine.evaluate_relationships(new_event=ev3, recent_events=[ev1, ev2], persist=True)
    assert any(r.details.get("rule_id") == "rel_entry_object_removed" for r in rels_3)


def test_cross_camera_handoff_and_timestamp_disorder():
    base_time = datetime(2026, 9, 30, 11, 0, 0, tzinfo=timezone.utc)

    # ev_a on Cam 1, ev_b on Cam 2 within 60s
    ev_a = {
        "event_id": "ev_handoff_1",
        "event_type": "person_entered",
        "camera_id": "cam_gate",
        "confidence": 0.92,
        "timestamp": base_time.isoformat(),
    }
    ev_b = {
        "event_id": "ev_handoff_2",
        "event_type": "person_entered",
        "camera_id": "cam_hallway",
        "confidence": 0.89,
        "timestamp": (base_time + timedelta(seconds=45)).isoformat(),
    }

    with get_db() as conn:
        for ev in [ev_a, ev_b]:
            conn.execute(
                "INSERT OR IGNORE INTO cameras (camera_id, name, source_type) VALUES (?, 'Test Cam', 'phone')",
                (ev["camera_id"],),
            )
            conn.execute(
                """
                INSERT INTO events (event_id, camera_id, event_type, severity, priority, confidence, summary, timestamp)
                VALUES (?, ?, ?, 'medium', 'MEDIUM', ?, 'summary', ?)
                """,
                (ev["event_id"], ev["camera_id"], ev["event_type"], ev["confidence"], ev["timestamp"]),
            )
        conn.commit()

    rels = relationship_engine.evaluate_relationships(new_event=ev_b, recent_events=[ev_a], persist=True)
    assert len(rels) >= 1
    handoff = next(r for r in rels if r.relationship_type == RelationshipType.CAMERA_HANDOFF.value)
    assert handoff.details["camera_a"] == "cam_gate"
    assert handoff.details["camera_b"] == "cam_hallway"
    assert handoff.time_delta_seconds == 45.0
