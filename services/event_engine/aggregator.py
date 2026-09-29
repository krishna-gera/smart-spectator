"""
Smart Spectator - Event Engine: Prediction Aggregator & Deduplication
Correlates overlapping temporal predictions to prevent duplicate event creation.
"""

from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Tuple, Set, Any
from shared.schemas.v1.models import EventPrediction, Event, EventStatus


class PredictionAggregator:
    """
    Correlates continuous sliding window predictions from SpectatorNet.
    Maintains active event correlation windows per camera to deduplicate events.
    """

    def __init__(self, event_window_seconds: float = 5.0):
        self.event_window_seconds = event_window_seconds
        # Key: (camera_id, event_type) -> active Event
        self._active_events: Dict[Tuple[str, str], Event] = {}

    def get_active_event(self, camera_id: str, event_type: str) -> Optional[Event]:
        return self._active_events.get((camera_id, event_type))

    def get_all_active_events(self) -> List[Event]:
        return list(self._active_events.values())

    def correlate(
        self, prediction: EventPrediction, now: Optional[float] = None
    ) -> Tuple[bool, Optional[Event]]:
        """
        Correlates an incoming EventPrediction with existing active events.
        Returns:
            (is_existing, event)
            If True, event is an existing active event that has been updated.
            If False, prediction is considered a candidate for a new event.
        """
        current_ts = now if now is not None else time.time()
        key = (prediction.camera_id, prediction.event_type)

        existing = self._active_events.get(key)
        if existing is not None:
            # Check if existing event is in an active/confirmed state
            if existing.status in (EventStatus.CONFIRMED, EventStatus.ACTIVE, EventStatus.DETECTED):
                # Check temporal window: elapsed since last update
                last_update_ts = existing.updated_at.replace(tzinfo=timezone.utc).timestamp()
                time_since_update = current_ts - last_update_ts

                # If within event window, or if track IDs overlap
                track_overlap = False
                if prediction.affected_tracks and existing.involved_track_ids:
                    set_pred = set(prediction.affected_tracks)
                    set_exist = set(existing.involved_track_ids)
                    if set_pred.intersection(set_exist):
                        track_overlap = True

                if time_since_update <= self.event_window_seconds or track_overlap:
                    # Correlated with existing event -> update it
                    self.update_existing_event(existing, prediction)
                    return True, existing

        return False, None

    def register_active_event(self, event: Event) -> None:
        """Registers a newly confirmed/active event in the active correlation map."""
        key = (event.camera_id, event.event_type)
        self._active_events[key] = event

    def update_existing_event(self, event: Event, prediction: EventPrediction) -> None:
        """Updates an existing event with new prediction information."""
        now_dt = datetime.now(timezone.utc)
        event.updated_at = now_dt
        event.end_time = prediction.end_time or now_dt
        # Track maximum confidence observed during the event
        event.confidence = max(event.confidence, prediction.confidence)
        
        # Merge affected tracks
        if prediction.affected_tracks:
            merged = set(event.involved_track_ids).union(set(prediction.affected_tracks))
            event.involved_track_ids = sorted(list(merged))

        # Merge prediction metadata
        if prediction.metadata:
            event.metadata.setdefault("prediction_count", 1)
            event.metadata["prediction_count"] += 1
            event.metadata["last_prediction_time"] = prediction.timestamp.isoformat()

    def remove_active_event(self, camera_id: str, event_type: str) -> Optional[Event]:
        """Removes an event from the active correlation map upon resolution or dismissal."""
        return self._active_events.pop((camera_id, event_type), None)

    def clear(self) -> None:
        self._active_events.clear()
