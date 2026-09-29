"""
Smart Spectator - Phase 4 Spatial Zones Unit & Integration Tests
Tests point-in-polygon, enter, exit, dwell time, loitering, and multi-camera isolation.
Conforms to Sections 13, 14, 15, 69 of Phase 4 specification.
"""

from datetime import datetime, timezone
import pytest

from shared.schemas.v1.models import Zone, Observation, TrackedObject
from services.event_engine.zones import point_inside_polygon, compute_centroid, ZoneEngine


def test_point_inside_polygon():
    # Unit square: [0.2, 0.2] to [0.6, 0.6]
    poly = [
        [0.2, 0.2],
        [0.6, 0.2],
        [0.6, 0.6],
        [0.2, 0.6],
    ]

    # Inside
    assert point_inside_polygon((0.4, 0.4), poly) is True
    # Outside
    assert point_inside_polygon((0.1, 0.1), poly) is False
    assert point_inside_polygon((0.8, 0.5), poly) is False
    assert point_inside_polygon((0.4, 0.9), poly) is False


def test_compute_centroid():
    bbox = [0.1, 0.2, 0.5, 0.8]
    cx, cy = compute_centroid(bbox)
    assert abs(cx - 0.3) < 1e-5
    assert abs(cy - 0.5) < 1e-5


def test_polygon_validation():
    ze = ZoneEngine()
    # Less than 3 points raises ValueError
    with pytest.raises(ValueError):
        ze.validate_polygon([[0.1, 0.1], [0.2, 0.2]])

    # Out of bounds (> 1.0) raises ValueError
    with pytest.raises(ValueError):
        ze.validate_polygon([[0.1, 0.1], [1.2, 0.5], [0.5, 0.5]])

    # Valid polygon passes
    ze.validate_polygon([[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]])


def test_zone_enter_exit_and_loitering():
    ze = ZoneEngine(default_loitering_seconds=3.0)

    # Add zone to memory
    test_zone = Zone(
        zone_id="door_zone",
        camera_id="cam_01",
        name="Front Door",
        polygon=[[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]],
        color="#38bdf8",
    )
    ze.add_or_update_zone_memory(test_zone)

    # Step 1: Person enters zone at t=100.0
    t0 = datetime.fromtimestamp(100.0, tz=timezone.utc)
    obs1 = Observation(
        observation_id="obs_1",
        camera_id="cam_01",
        timestamp=t0,
        frame_index=1,
        tracked_objects=[
            TrackedObject(
                track_id=1,
                camera_id="cam_01",
                class_name="person",
                current_bbox=[0.3, 0.3, 0.5, 0.5], # centroid (0.4, 0.4) inside
                confidence=0.9,
                first_seen_timestamp=t0,
                last_seen_timestamp=t0,
            )
        ],
    )
    events = ze.process_observation(obs1)
    assert len(events) == 1
    assert events[0]["type"] == "ZONE_ENTER"
    assert events[0]["track_id"] == 1
    assert events[0]["zone_id"] == "door_zone"

    # Step 2: Person remains in zone at t=102.0 (dwell = 2.0s < 3.0s threshold)
    t1 = datetime.fromtimestamp(102.0, tz=timezone.utc)
    obs2 = Observation(
        observation_id="obs_2",
        camera_id="cam_01",
        timestamp=t1,
        frame_index=2,
        tracked_objects=[
            TrackedObject(
                track_id=1,
                camera_id="cam_01",
                class_name="person",
                current_bbox=[0.35, 0.35, 0.45, 0.45],
                confidence=0.9,
                first_seen_timestamp=t0,
                last_seen_timestamp=t1,
            )
        ],
    )
    events2 = ze.process_observation(obs2)
    assert len(events2) == 0  # No loitering yet

    # Step 3: Person remains in zone at t=104.0 (dwell = 4.0s >= 3.0s threshold) -> ZONE_LOITERING
    t2 = datetime.fromtimestamp(104.0, tz=timezone.utc)
    obs3 = Observation(
        observation_id="obs_3",
        camera_id="cam_01",
        timestamp=t2,
        frame_index=3,
        tracked_objects=[
            TrackedObject(
                track_id=1,
                camera_id="cam_01",
                class_name="person",
                current_bbox=[0.35, 0.35, 0.45, 0.45],
                confidence=0.9,
                first_seen_timestamp=t0,
                last_seen_timestamp=t2,
            )
        ],
    )
    events3 = ze.process_observation(obs3)
    assert len(events3) == 1
    assert events3[0]["type"] == "ZONE_LOITERING"
    assert events3[0]["dwell_seconds"] == 4.0

    # Step 4: Person exits zone at t=107.0 (outside zone: bbox at [0.8, 0.8, 0.9, 0.9])
    t3 = datetime.fromtimestamp(107.0, tz=timezone.utc)
    obs4 = Observation(
        observation_id="obs_4",
        camera_id="cam_01",
        timestamp=t3,
        frame_index=4,
        tracked_objects=[
            TrackedObject(
                track_id=1,
                camera_id="cam_01",
                class_name="person",
                current_bbox=[0.8, 0.8, 0.9, 0.9], # centroid (0.85, 0.85) outside
                confidence=0.9,
                first_seen_timestamp=t0,
                last_seen_timestamp=t3,
            )
        ],
    )
    events4 = ze.process_observation(obs4)
    assert len(events4) == 1
    assert events4[0]["type"] == "ZONE_EXIT"
    assert events4[0]["total_dwell_seconds"] == 4.0


def test_multi_camera_zone_isolation():
    ze = ZoneEngine()
    z_cam1 = Zone(
        zone_id="cam1_zone",
        camera_id="cam_01",
        name="Cam1 Zone",
        polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )
    ze.add_or_update_zone_memory(z_cam1)

    # Observation on cam_02 should NOT trigger cam_01 zone
    t0 = datetime.now(timezone.utc)
    obs_cam2 = Observation(
        observation_id="obs_c2",
        camera_id="cam_02",
        timestamp=t0,
        frame_index=1,
        tracked_objects=[
            TrackedObject(
                track_id=99,
                camera_id="cam_02",
                class_name="person",
                current_bbox=[0.2, 0.2, 0.5, 0.5],
                confidence=0.9,
                first_seen_timestamp=t0,
                last_seen_timestamp=t0,
            )
        ],
    )
    events = ze.process_observation(obs_cam2)
    assert len(events) == 0
