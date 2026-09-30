"""
Smart Spectator - Semantic Event Model
Conforms to Sections 2 & 11 of Phase 10 Specification.
Defines normalized, structured semantic event representations:
Observation -> Prediction -> Event -> Context -> Incident.
Zero external network/LLM dependencies; 100% deterministic local schema.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class SemanticEntity:
    entity_type: str  # "person", "vehicle", "object", "camera"
    track_id: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticLocation:
    camera_id: str
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None  # "detection", "exclusion", "loitering", "transit"
    coordinates: Optional[List[float]] = None  # [norm_x, norm_y]


@dataclass
class SemanticEvent:
    """
    Normalized semantic representation of an event.
    Provides structured foundation for context synthesis and natural-language query matching.
    """
    entity: str  # e.g., "person", "vehicle", "camera"
    action: str  # e.g., "entered", "loitered", "left", "transit", "hesitated", "blocked"
    location: str  # e.g., "front_door:restricted_zone"
    time: str  # ISO-8601 timestamp
    duration: float  # In seconds
    confidence: float  # In [0.0, 1.0]
    camera_id: str
    zone_id: Optional[str] = None
    event_id: Optional[str] = None
    priority: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticEvent":
        return cls(
            entity=data.get("entity", "unknown"),
            action=data.get("action", "detected"),
            location=data.get("location", "unknown"),
            time=data.get("time", datetime.now(timezone.utc).isoformat()),
            duration=float(data.get("duration", 0.0)),
            confidence=float(data.get("confidence", 0.0)),
            camera_id=data.get("camera_id", ""),
            zone_id=data.get("zone_id"),
            event_id=data.get("event_id"),
            priority=data.get("priority", "MEDIUM"),
            attributes=data.get("attributes", {}),
        )


def event_record_to_semantic(
    event_id: str,
    event_type: str,
    camera_id: str,
    confidence: float,
    priority: str = "MEDIUM",
    zone_id: Optional[str] = None,
    zone_name: Optional[str] = None,
    track_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    timestamp: Optional[datetime] = None,
    details: Optional[Dict[str, Any]] = None,
) -> SemanticEvent:
    """Converts a raw or database EventRecord into a normalized SemanticEvent."""
    details = details or {}
    
    # Infer entity from event_type and details
    lower_type = event_type.lower()
    if "vehicle" in lower_type or "car" in lower_type:
        entity = "vehicle"
    elif "camera" in lower_type or "tamper" in lower_type or "block" in lower_type:
        entity = "camera"
    elif "object" in lower_type:
        entity = "object"
    else:
        entity = "person"

    # Infer action
    if "enter" in lower_type or "intrusion" in lower_type or "entry" in lower_type:
        action = "entered"
    elif "exit" in lower_type or "left" in lower_type:
        action = "left"
    elif "loiter" in lower_type:
        action = "loitered"
    elif "block" in lower_type:
        action = "blocked"
    elif "recover" in lower_type:
        action = "recovered"
    elif "remov" in lower_type:
        action = "removed"
    elif "motion" in lower_type or "transit" in lower_type:
        action = "transit"
    else:
        action = lower_type

    # Format location string
    loc_parts = [camera_id]
    if zone_name:
        loc_parts.append(zone_name)
    elif zone_id:
        loc_parts.append(zone_id)
    location_str = ":".join(loc_parts)

    # Compute duration
    duration = 0.0
    if start_time and end_time:
        duration = max(0.0, (end_time - start_time).total_seconds())
    elif details.get("duration_seconds"):
        duration = float(details["duration_seconds"])

    t_str = (timestamp or start_time or datetime.now(timezone.utc)).isoformat()

    return SemanticEvent(
        entity=entity,
        action=action,
        location=location_str,
        time=t_str,
        duration=round(duration, 2),
        confidence=round(confidence, 3),
        camera_id=camera_id,
        zone_id=zone_id,
        event_id=event_id,
        priority=priority.upper(),
        attributes={
            "track_id": track_id,
            "raw_event_type": event_type,
            "zone_name": zone_name,
            **details,
        },
    )
