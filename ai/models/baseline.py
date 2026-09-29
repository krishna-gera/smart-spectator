"""
Smart Spectator - Rule-Based Temporal Baseline Classifier
Implements non-neural state-machine heuristic baseline for event classification.
Conforms to Section 36 of Phase 3 specification.
Used as an honest, scientific performance benchmark against SpectatorNet.
"""

from typing import List, Dict, Any, Optional
import numpy as np

from shared.schemas.v1.models import Observation, EventPrediction
from ai.datasets.constants import CLASS_TO_ID, DEFAULT_EVENT_CLASSES


Tuple_Prediction = tuple[str, float, int]


class RuleBasedTemporalClassifier:
    """
    Non-neural baseline classifier applying deterministic temporal heuristics
    to sequence windows of Observations.
    """

    def __init__(self, fps: float = 5.0):
        self.fps = fps

    def predict_sequence(self, observations: List[Observation]) -> Tuple_Prediction:
        """
        Classifies a temporal sequence using state-transition heuristics.
        Returns (predicted_class_name, confidence, predicted_class_id).
        """
        if not observations:
            return "NORMAL_BACKGROUND", 0.5, CLASS_TO_ID["NORMAL_BACKGROUND"]

        # 1. Check Camera Blocked (low detections and camera_blocked flag)
        blocked_frames = 0
        for obs in observations:
            if hasattr(obs, "scene_state") and obs.scene_state.get("camera_blocked", False):
                blocked_frames += 1
        if blocked_frames >= (len(observations) // 2):
            return "CAMERA_BLOCKED", 0.95, CLASS_TO_ID["CAMERA_BLOCKED"]

        # 2. Track dynamics across sequence
        first_obs = observations[0]
        last_obs = observations[-1]
        mid_obs = observations[len(observations) // 2]

        def get_persons(obs: Observation) -> List[Any]:
            return [t for t in obs.tracked_objects if t.class_name.lower() == "person"]

        def get_items(obs: Observation) -> List[Any]:
            return [t for t in obs.tracked_objects if t.class_name.lower() != "person"]

        first_persons = get_persons(first_obs)
        last_persons = get_persons(last_obs)
        first_items = get_items(first_obs)
        last_items = get_items(last_obs)

        # 3. Person Entered: No person initially, person present at end
        if len(first_persons) == 0 and len(last_persons) > 0:
            return "PERSON_ENTERED", 0.90, CLASS_TO_ID["PERSON_ENTERED"]

        # 4. Person Left: Person present initially, gone at end
        if len(first_persons) > 0 and len(last_persons) == 0:
            return "PERSON_LEFT", 0.90, CLASS_TO_ID["PERSON_LEFT"]

        # 5. Object Removed: Item present initially, gone at end
        if len(first_items) > 0 and len(last_items) == 0:
            return "OBJECT_REMOVED", 0.88, CLASS_TO_ID["OBJECT_REMOVED"]

        # 6. Object Moved / Task Completed
        if len(first_items) > 0 and len(last_items) > 0:
            # Check displacement between first and last
            first_bbox = first_items[0].current_bbox
            last_bbox = last_items[0].current_bbox
            dx = abs(last_bbox[0] - first_bbox[0])
            dy = abs(last_bbox[1] - first_bbox[1])
            displacement = np.sqrt(dx * dx + dy * dy)
            if displacement > 0.15:
                return "OBJECT_MOVED", 0.85, CLASS_TO_ID["OBJECT_MOVED"]

        # 7. Zone Loitering: Person present throughout whole sequence with very low velocity
        if len(first_persons) > 0 and len(last_persons) > 0:
            total_speed = sum(
                np.sqrt(t.velocity_vector[0]**2 + t.velocity_vector[1]**2)
                for t in last_persons if t.velocity_vector
            )
            if total_speed < 0.05:
                return "ZONE_LOITERING", 0.85, CLASS_TO_ID["ZONE_LOITERING"]

        # 8. Object Present: Items present and stationary
        if len(first_items) > 0 and len(last_items) > 0:
            return "OBJECT_PRESENT", 0.80, CLASS_TO_ID["OBJECT_PRESENT"]

        # Default fallback
        return "NORMAL_BACKGROUND", 0.70, CLASS_TO_ID["NORMAL_BACKGROUND"]


Tuple_Prediction = tuple[str, float, int]
