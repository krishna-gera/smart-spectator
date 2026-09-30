"""
Phase 10 Tests — Semantic Event Model & Normalization
Conforms to Sections 2, 11 & 37 of Phase 10 Specification.
Validates:
1. Normalization of raw observations and events into SemanticEvent schemas.
2. Inferred entity, action, duration, and formatted location strings.
3. Serialization to and deserialization from dictionary representation.
"""

from datetime import datetime, timezone, timedelta
import pytest

from services.event_engine.semantic_model import (
    SemanticEvent,
    event_record_to_semantic,
)


def test_semantic_event_serialization_and_deserialization():
    now_iso = datetime.now(timezone.utc).isoformat()
    se = SemanticEvent(
        entity="person",
        action="entered",
        location="cam-front:lobby_zone",
        time=now_iso,
        duration=4.2,
        confidence=0.94,
        camera_id="cam-front",
        zone_id="lobby_zone",
        event_id="ev_test_101",
        priority="HIGH",
        attributes={"track_id": 42},
    )

    data = se.to_dict()
    assert data["entity"] == "person"
    assert data["action"] == "entered"
    assert data["location"] == "cam-front:lobby_zone"
    assert data["confidence"] == 0.94
    assert data["priority"] == "HIGH"

    restored = SemanticEvent.from_dict(data)
    assert restored.event_id == se.event_id
    assert restored.duration == 4.2
    assert restored.attributes["track_id"] == 42


def test_event_record_to_semantic_conversion():
    t0 = datetime.now(timezone.utc) - timedelta(seconds=12)
    t1 = datetime.now(timezone.utc)

    # 1. Person entered event
    se1 = event_record_to_semantic(
        event_id="ev_001",
        event_type="PERSON_ENTERED",
        camera_id="cam_back_gate",
        confidence=0.88,
        priority="CRITICAL",
        zone_id="perimeter_zone",
        zone_name="Perimeter Boundary",
        track_id=10,
        start_time=t0,
        end_time=t1,
    )
    assert se1.entity == "person"
    assert se1.action == "entered"
    assert se1.location == "cam_back_gate:Perimeter Boundary"
    assert se1.priority == "CRITICAL"
    assert se1.duration == 12.0
    assert se1.confidence == 0.88

    # 2. Camera blocked event
    se2 = event_record_to_semantic(
        event_id="ev_002",
        event_type="CAMERA_BLOCKED",
        camera_id="cam_lobby",
        confidence=0.95,
        priority="HIGH",
    )
    assert se2.entity == "camera"
    assert se2.action == "blocked"
    assert se2.location == "cam_lobby"

    # 3. Object removed event
    se3 = event_record_to_semantic(
        event_id="ev_003",
        event_type="OBJECT_REMOVED",
        camera_id="cam_vault",
        confidence=0.79,
        priority="HIGH",
    )
    assert se3.entity == "object"
    assert se3.action == "removed"
