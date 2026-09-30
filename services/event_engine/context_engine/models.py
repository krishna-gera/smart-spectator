"""
Smart Spectator - Context Engine Models
Conforms to Section 5 of Phase 10 Specification.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class EnvironmentalContext:
    timestamp: str
    hour_of_day: int
    day_of_week: int
    is_weekend: bool
    is_after_hours: bool
    camera_id: str
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    recent_events_count_5m: int = 0
    active_events_count: int = 0
    device_state: Dict[str, Any] = field(default_factory=dict)
    system_state: Dict[str, Any] = field(default_factory=dict)
    future_context: Dict[str, Any] = field(default_factory=lambda: {
        "weather": "LOCAL_UNSET",
        "calendar_event": "NONE",
        "external_sensors": {},
    })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
