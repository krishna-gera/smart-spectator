"""
Smart Spectator - Event Engine: Confidence Filtering
Applies configurable per-event-type thresholds to filter noisy predictions.
"""

from typing import Dict, Any, Optional
from shared.schemas.v1.models import EventPrediction


# Initial default thresholds per Phase 4 specification (configurable at runtime)
DEFAULT_CONFIDENCE_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "NORMAL_BACKGROUND": {
        "min_prediction": 0.50,
        "confirmation": 0.60,
        "high_confidence": 0.85,
    },
    "OBJECT_PRESENT": {
        "min_prediction": 0.65,
        "confirmation": 0.75,
        "high_confidence": 0.85,
    },
    "OBJECT_REMOVED": {
        "min_prediction": 0.70,
        "confirmation": 0.80,
        "high_confidence": 0.90,
    },
    "OBJECT_MOVED": {
        "min_prediction": 0.70,
        "confirmation": 0.75,
        "high_confidence": 0.85,
    },
    "PERSON_ENTERED": {
        "min_prediction": 0.70,
        "confirmation": 0.75,
        "high_confidence": 0.90,
    },
    "PERSON_LEFT": {
        "min_prediction": 0.65,
        "confirmation": 0.75,
        "high_confidence": 0.85,
    },
    "ZONE_LOITERING": {
        "min_prediction": 0.70,
        "confirmation": 0.75,
        "high_confidence": 0.90,
    },
    "CAMERA_BLOCKED": {
        "min_prediction": 0.75,
        "confirmation": 0.85,
        "high_confidence": 0.95,
    },
    "TASK_COMPLETED": {
        "min_prediction": 0.70,
        "confirmation": 0.80,
        "high_confidence": 0.90,
    },
}

GLOBAL_FALLBACK_THRESHOLDS = {
    "min_prediction": 0.70,
    "confirmation": 0.80,
    "high_confidence": 0.90,
}


class ConfidenceFilter:
    """
    Evaluates SpectatorNet EventPrediction confidence against configurable per-class thresholds.
    """

    def __init__(self, custom_thresholds: Optional[Dict[str, Dict[str, float]]] = None):
        self._thresholds: Dict[str, Dict[str, float]] = {}
        for k, v in DEFAULT_CONFIDENCE_THRESHOLDS.items():
            self._thresholds[k] = v.copy()
        if custom_thresholds:
            for k, v in custom_thresholds.items():
                if k not in self._thresholds:
                    self._thresholds[k] = GLOBAL_FALLBACK_THRESHOLDS.copy()
                self._thresholds[k].update(v)

    def get_thresholds(self, event_type: str) -> Dict[str, float]:
        return self._thresholds.get(event_type, GLOBAL_FALLBACK_THRESHOLDS.copy())

    def update_thresholds(self, event_type: str, thresholds: Dict[str, float]) -> None:
        if event_type not in self._thresholds:
            self._thresholds[event_type] = GLOBAL_FALLBACK_THRESHOLDS.copy()
        self._thresholds[event_type].update(thresholds)

    def is_candidate(self, prediction: EventPrediction) -> bool:
        """Determines if prediction meets minimum threshold to enter debouncing."""
        th = self.get_thresholds(prediction.event_type)
        return prediction.confidence >= th.get("min_prediction", 0.70)

    def is_confirmed(self, prediction: EventPrediction) -> bool:
        """Determines if prediction confidence is sufficient for confirmation."""
        th = self.get_thresholds(prediction.event_type)
        return prediction.confidence >= th.get("confirmation", 0.80)

    def is_high_confidence(self, prediction: EventPrediction) -> bool:
        th = self.get_thresholds(prediction.event_type)
        return prediction.confidence >= th.get("high_confidence", 0.90)
