"""
Smart Spectator - Event Engine: Temporal Debouncer
Filters noisy transient predictions by requiring consecutive confirmations,
and triggers automatic resolution when prediction streaks cease.
"""

import time
from typing import Dict, Tuple, Optional, List
from shared.schemas.v1.models import EventPrediction


class TemporalDebouncer:
    """
    Maintains prediction streaks per (camera_id, event_type).
    Ensures minimum consecutive predictions before confirmation, and detects
    inactivity timeouts for event resolution.
    """

    def __init__(
        self,
        min_consecutive: int = 2,
        resolution_timeout_seconds: float = 3.0,
    ):
        self.min_consecutive = min_consecutive
        self.resolution_timeout_seconds = resolution_timeout_seconds

        # Key: (camera_id, event_type) -> streak count
        self._streaks: Dict[Tuple[str, str], int] = {}
        # Key: (camera_id, event_type) -> last prediction timestamp
        self._last_seen: Dict[Tuple[str, str], float] = {}
        # Key: (camera_id, event_type) -> first prediction timestamp of streak
        self._streak_start: Dict[Tuple[str, str], float] = {}

    def record_positive_prediction(
        self, camera_id: str, event_type: str, timestamp: Optional[float] = None
    ) -> Tuple[bool, int]:
        """
        Records a positive prediction.
        Returns: (is_confirmed, current_streak)
        """
        now = timestamp if timestamp is not None else time.time()
        key = (camera_id, event_type)

        streak = self._streaks.get(key, 0) + 1
        self._streaks[key] = streak
        self._last_seen[key] = now
        if streak == 1:
            self._streak_start[key] = now

        is_confirmed = streak >= self.min_consecutive
        return is_confirmed, streak

    def get_streak(self, camera_id: str, event_type: str) -> int:
        return self._streaks.get((camera_id, event_type), 0)

    def get_streak_start_time(self, camera_id: str, event_type: str) -> Optional[float]:
        return self._streak_start.get((camera_id, event_type))

    def reset_streak(self, camera_id: str, event_type: str) -> None:
        key = (camera_id, event_type)
        self._streaks.pop(key, None)
        self._last_seen.pop(key, None)
        self._streak_start.pop(key, None)

    def check_resolution_timeouts(
        self, active_event_keys: List[Tuple[str, str]], current_time: Optional[float] = None
    ) -> List[Tuple[str, str]]:
        """
        Identifies active events that have timed out due to absent positive predictions.
        Returns list of (camera_id, event_type) to resolve.
        """
        now = current_time if current_time is not None else time.time()
        timed_out = []

        for key in active_event_keys:
            last = self._last_seen.get(key, 0.0)
            if now - last >= self.resolution_timeout_seconds:
                timed_out.append(key)

        return timed_out
