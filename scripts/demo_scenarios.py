"""
Smart Spectator - Deterministic Challenge Demonstration Harness
Conforms to Sections 77, 78, 80 of Phase 7 Specification.
Provides reproducible live scenarios:
  1. PERSON_ENTERED (Zone intrusion)
  2. OBJECT_REMOVED (Asset theft / disappearance)
  3. ZONE_LOITERING (Restricted perimeter dwell threshold exceeded)
All events are marked with 'is_demo': True in DEMO_MODE.
"""

import argparse
from datetime import datetime, timezone
import json
import time
from typing import Dict, Any

import numpy as np

from shared.schemas.v1.models import Observation, TrackedObject, Zone, EventPrediction
from ai.models.predictor import SpectatorNetPredictor
from services.event_engine import EventEngine
from services.event_engine.recorder import RecordingManager
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database, db_session


def run_scenario_person_entered(engine: EventEngine, rec_mgr: RecordingManager, cam_id: str):
    print("\n" + "=" * 60)
    print("▶ RUNNING SCENARIO 1: PERSON_ENTERED")
    print("=" * 60)
    t0 = time.time()
    dummy_frame = np.full((120, 160, 3), 110, dtype=np.uint8)

    # Ingest frames to rolling buffer
    for i in range(15):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t0 + i * 0.1, frame_index=i)

    now = datetime.now(timezone.utc)
    pred = EventPrediction(
        camera_id=cam_id,
        event_type="PERSON_ENTERED",
        confidence=0.91,
        timestamp=now,
        affected_tracks=[101],
        metadata={"is_demo": True, "scenario": "PERSON_ENTERED"},
    )

    print(f"  [AI Engine] Emitting SpectatorNet prediction: {pred.event_type} (conf: {pred.confidence})")
    # Feed consecutively for debouncing
    engine._handle_prediction(pred)
    engine._handle_prediction(pred)

    with db_session() as conn:
        cursor = conn.execute(
            "SELECT * FROM events WHERE camera_id = ? AND event_type = 'PERSON_ENTERED' ORDER BY timestamp DESC LIMIT 1",
            (cam_id,)
        )
        ev = cursor.fetchone()
        if ev:
            print(f"  [Event Engine] Confirmed Event: ID={ev['event_id']}, Status={ev['status']}, Severity={ev['severity']}")
            print(f"  [Explanation]: {ev.get('explanation')}")
        else:
            print("  [Error] Event was not created!")


def run_scenario_object_removed(engine: EventEngine, rec_mgr: RecordingManager, cam_id: str):
    print("\n" + "=" * 60)
    print("▶ RUNNING SCENARIO 2: OBJECT_REMOVED")
    print("=" * 60)
    t0 = time.time()
    dummy_frame = np.full((120, 160, 3), 140, dtype=np.uint8)

    for i in range(15):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t0 + i * 0.1, frame_index=i)

    now = datetime.now(timezone.utc)
    pred = EventPrediction(
        camera_id=cam_id,
        event_type="OBJECT_REMOVED",
        confidence=0.89,
        timestamp=now,
        affected_tracks=[202],
        metadata={"is_demo": True, "scenario": "OBJECT_REMOVED"},
    )

    print(f"  [AI Engine] Emitting SpectatorNet prediction: {pred.event_type} (conf: {pred.confidence})")
    engine._handle_prediction(pred)
    engine._handle_prediction(pred)

    with db_session() as conn:
        cursor = conn.execute(
            "SELECT * FROM events WHERE camera_id = ? AND event_type = 'OBJECT_REMOVED' ORDER BY timestamp DESC LIMIT 1",
            (cam_id,)
        )
        ev = cursor.fetchone()
        if ev:
            print(f"  [Event Engine] Confirmed Event: ID={ev['event_id']}, Status={ev['status']}, Severity={ev['severity']}")
            print(f"  [Explanation]: {ev.get('explanation')}")
        else:
            print("  [Error] Event was not created!")


def run_scenario_zone_loitering(engine: EventEngine, rec_mgr: RecordingManager, cam_id: str):
    print("\n" + "=" * 60)
    print("▶ RUNNING SCENARIO 3: ZONE_LOITERING")
    print("=" * 60)

    # Setup polygon zone
    test_zone = Zone(
        zone_id="demo_restricted_zone",
        camera_id=cam_id,
        name="Demo Restricted Area",
        polygon=[[0.1, 0.1], [0.7, 0.1], [0.7, 0.7], [0.1, 0.7]],
        color="#f43f5e",
    )
    engine.zone_engine.add_or_update_zone_memory(test_zone)
    engine.zone_engine.default_loitering_seconds = 2.0

    t0 = time.time()
    dummy_frame = np.full((120, 160, 3), 180, dtype=np.uint8)
    for i in range(10):
        rec_mgr.ingest_frame(cam_id, dummy_frame, timestamp=t0 + i * 0.1, frame_index=i)

    # Step 1: Person enters zone
    obs1 = Observation(
        observation_id="demo_obs_1",
        camera_id=cam_id,
        timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
        frame_index=1,
        tracked_objects=[
            TrackedObject(
                track_id=303,
                camera_id=cam_id,
                class_name="person",
                current_bbox=[0.2, 0.2, 0.5, 0.5],
                confidence=0.95,
                first_seen_timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
                last_seen_timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
            )
        ],
    )
    engine._handle_observation(obs1)

    # Step 2: Person dwells past 2.0s threshold
    obs2 = Observation(
        observation_id="demo_obs_2",
        camera_id=cam_id,
        timestamp=datetime.fromtimestamp(t0 + 2.5, tz=timezone.utc),
        frame_index=2,
        tracked_objects=[
            TrackedObject(
                track_id=303,
                camera_id=cam_id,
                class_name="person",
                current_bbox=[0.2, 0.2, 0.5, 0.5],
                confidence=0.95,
                first_seen_timestamp=datetime.fromtimestamp(t0, tz=timezone.utc),
                last_seen_timestamp=datetime.fromtimestamp(t0 + 2.5, tz=timezone.utc),
            )
        ],
    )
    engine._handle_observation(obs2)
    engine._handle_observation(obs2)

    with db_session() as conn:
        cursor = conn.execute(
            "SELECT * FROM events WHERE camera_id = ? AND event_type = 'ZONE_LOITERING' ORDER BY timestamp DESC LIMIT 1",
            (cam_id,)
        )
        ev = cursor.fetchone()
        if ev:
            print(f"  [Event Engine] Confirmed Event: ID={ev['event_id']}, Zone={ev['zone_id']}, Status={ev['status']}")
            print(f"  [Explanation]: {ev.get('explanation')}")
        else:
            print("  [Error] Loitering event was not created!")


def main():
    parser = argparse.ArgumentParser(description="Smart Spectator Demo Scenarios Runner")
    parser.add_argument("--scenario", choices=["1", "2", "3", "all"], default="all", help="Scenario number to run")
    parser.add_argument("--camera", default="cam_demo_01", help="Camera ID to target")
    args = parser.parse_args()

    init_database()

    # Pre-seed camera in DB
    with db_session() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cameras (camera_id, name, source_type, status) VALUES (?, ?, 'phone', 'streaming')",
            (args.camera, "Demo Camera Node")
        )

    rec_mgr = RecordingManager(
        recordings_dir=settings.RECORDINGS_DIR,
        snapshots_dir=settings.SNAPSHOTS_DIR,
        pre_roll_seconds=2.0,
        post_roll_seconds=1.0,
    )
    engine = EventEngine(recording_manager=rec_mgr)
    engine.start()

    try:
        if args.scenario in ("1", "all"):
            run_scenario_person_entered(engine, rec_mgr, args.camera)
        if args.scenario in ("2", "all"):
            run_scenario_object_removed(engine, rec_mgr, args.camera)
        if args.scenario in ("3", "all"):
            run_scenario_zone_loitering(engine, rec_mgr, args.camera)

        print("\n" + "=" * 60)
        print("✓ ALL DEMO SCENARIOS EXECUTED SUCCESSFULLY")
        print("=" * 60)
    finally:
        engine.stop()


if __name__ == "__main__":
    main()
