"""
Smart Spectator - Observation Builder
Synthesizes Level 1 Detections and Level 2 Tracks into versioned Observation contracts.
Conforms to shared/schemas/v1/models.py
"""

import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from shared.schemas.v1.models import Observation, Detection, TrackedObject


class ObservationBuilder:
    """Constructs structured Observation objects for downstream Event Engine and dataset ingestion."""

    @staticmethod
    def build(
        camera_id: str,
        frame_index: int,
        detections: List[Detection],
        tracked_objects: List[TrackedObject],
        inference_telemetry: Optional[Dict[str, Any]] = None
    ) -> Observation:
        # Build spatial scene summary
        class_counts: Dict[str, int] = {}
        for d in detections:
            class_counts[d.class_name] = class_counts.get(d.class_name, 0) + 1

        active_track_ids = [t.track_id for t in tracked_objects if t.is_active]

        scene_state = {
            "total_detected_objects": len(detections),
            "total_active_tracks": len(active_track_ids),
            "class_distribution": class_counts,
            "active_track_ids": active_track_ids,
            "inference": inference_telemetry or {}
        }

        return Observation(
            observation_id=f"obs_{uuid.uuid4().hex[:12]}",
            camera_id=camera_id,
            timestamp=datetime.now(timezone.utc),
            frame_index=frame_index,
            detections=detections,
            tracked_objects=tracked_objects,
            scene_state=scene_state
        )
