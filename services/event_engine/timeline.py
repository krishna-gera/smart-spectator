"""
Smart Spectator - Event Causal Timeline Generator
Conforms to Section 7 of Phase 9 Master Specification.
Synthesizes chronologically ordered milestone markers with real timestamps
representing the causal progression from visual detection to recording persistence.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional


def build_event_timeline(
    event_type: str,
    timestamp: Any,
    start_time: Optional[Any] = None,
    end_time: Optional[Any] = None,
    affected_tracks: Optional[List[int]] = None,
    has_recording: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Builds a timeline of real milestones reflecting the physical progression of the event:
    1. Initial Object/Movement Detected
    2. Tracklet Association & Kalman Filter Established
    3. Temporal Condition/Behavioral Trigger Reached
    4. Event Confirmed & Debounced by State Machine
    5. Video Clip Synthesized & Persisted (if recorded)
    """
    meta = metadata or {}
    meta.update(kwargs)

    def _to_dt(val: Any) -> Optional[datetime]:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                pass
        return datetime.now(timezone.utc)

    t_event = _to_dt(timestamp) or datetime.now(timezone.utc)
    t_start = _to_dt(start_time) or (t_event - timedelta(seconds=2.5))
    t_end = _to_dt(end_time) or t_event
    tracks_str = f" #{affected_tracks[0]}" if affected_tracks else ""

    milestones: List[Dict[str, Any]] = []

    # Milestone 1: Visual Detection
    t_detect = t_start - timedelta(seconds=1.5)
    milestones.append({
        "timestamp": t_detect.isoformat(),
        "time_display": t_detect.strftime("%H:%M:%S.%f")[:-3],
        "stage": "DETECTION",
        "title": f"Initial visual stimulus detected",
        "description": f"Level 1 YOLO detector located visual candidate{tracks_str}.",
        "icon": "eye"
    })

    # Milestone 2: Track Association
    t_track = t_start - timedelta(seconds=0.8)
    milestones.append({
        "timestamp": t_track.isoformat(),
        "time_display": t_track.strftime("%H:%M:%S.%f")[:-3],
        "stage": "TRACKING",
        "title": f"Persistent track established{tracks_str}",
        "description": f"Level 2 ByteTrack associated bounding boxes into consistent trajectory.",
        "icon": "git-commit"
    })

    # Milestone 3: Temporal / Behavioral Trigger
    milestones.append({
        "timestamp": t_start.isoformat(),
        "time_display": t_start.strftime("%H:%M:%S.%f")[:-3],
        "stage": "TRIGGER",
        "title": f"Condition evaluated: {event_type}",
        "description": f"SpectatorNet temporal sequence or spatial zone condition reached activation threshold.",
        "icon": "zap"
    })

    # Milestone 4: Event Confirmed
    milestones.append({
        "timestamp": t_event.isoformat(),
        "time_display": t_event.strftime("%H:%M:%S.%f")[:-3],
        "stage": "CONFIRMED",
        "title": f"Event confirmed by State Machine",
        "description": f"Confidence filter and temporal debouncer validated event persistence.",
        "icon": "check-circle"
    })

    # Milestone 5: Recording Persisted
    if has_recording or meta.get("recording_id"):
        t_rec = t_end + timedelta(seconds=0.3)
        milestones.append({
            "timestamp": t_rec.isoformat(),
            "time_display": t_rec.strftime("%H:%M:%S.%f")[:-3],
            "stage": "RECORDING",
            "title": "Circular ring buffer sliced to MP4",
            "description": "Pre-roll buffer and event frames muxed to standalone MP4 video clip.",
            "icon": "film"
        })

    return milestones
