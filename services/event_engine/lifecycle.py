"""
Smart Spectator - Event Engine: Lifecycle Explanations & Summaries
Generates deterministic, human-readable explanations from structured event metadata.
Conforms to Section 87 of Phase 4 specification.
"""

from typing import Dict, Any, Optional, List
from shared.schemas.v1.models import EventPrediction


def generate_event_explanation(
    event_type: str,
    confidence: float,
    camera_name: str,
    zone_name: Optional[str] = None,
    affected_tracks: Optional[List[int]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates deterministic human-readable explanation from structured event metadata.
    Zero LLM dependencies.
    """
    meta = metadata or {}
    cam_str = camera_name or "Camera"
    conf_pct = int(confidence * 100)

    if event_type == "OBJECT_REMOVED":
        duration = meta.get("presence_duration_seconds")
        dur_str = f" after being present for {duration:.1f}s" if duration is not None else ""
        tracks_str = f" (Track #{affected_tracks[0]})" if affected_tracks else ""
        return f"Tracked object{tracks_str} disappeared from {cam_str}{dur_str} (Confidence: {conf_pct}%)."

    elif event_type == "PERSON_ENTERED":
        if zone_name:
            return f"A person track entered the '{zone_name}' zone on {cam_str} (Confidence: {conf_pct}%)."
        return f"A person track entered the scene on {cam_str} (Confidence: {conf_pct}%)."

    elif event_type == "PERSON_LEFT":
        if zone_name:
            return f"Person exited the '{zone_name}' zone on {cam_str}."
        return f"Person exited the monitored area on {cam_str}."

    elif event_type == "ZONE_LOITERING":
        dwell = meta.get("dwell_seconds", 30.0)
        zn = f"'{zone_name}' zone" if zone_name else "monitored zone"
        return f"Person remained inside {zn} on {cam_str} for {dwell:.0f} seconds (Threshold exceeded)."

    elif event_type == "CAMERA_BLOCKED":
        return f"Optical obstruction or severe camera blockage detected on {cam_str} across consecutive frames."

    elif event_type == "OBJECT_MOVED":
        dist = meta.get("displacement_normalized")
        dist_str = f" by {dist:.2f} relative distance" if dist is not None else ""
        return f"Tracked object displacement detected on {cam_str}{dist_str} (Confidence: {conf_pct}%)."

    elif event_type == "OBJECT_PRESENT":
        return f"Monitored object confirmed present on {cam_str}."

    elif event_type == "CAMERA_CONNECTED":
        return f"Camera '{cam_str}' established connection to the local Hub."

    elif event_type == "CAMERA_DISCONNECTED":
        return f"Camera '{cam_str}' disconnected or stream was interrupted."

    elif event_type == "CAMERA_STREAM_ERROR":
        err = meta.get("error", "Stream decode failure")
        return f"Stream error on {cam_str}: {err}."

    return f"Event '{event_type}' detected on {cam_str} (Confidence: {conf_pct}%)."
