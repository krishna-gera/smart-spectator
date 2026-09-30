"""
Smart Spectator - Event Relationship Models
Conforms to Section 3 of Phase 10 Specification.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
import uuid


class RelationshipType(str, Enum):
    FOLLOWED_BY = "followed_by"
    CAMERA_HANDOFF = "camera_handoff"
    CO_OCCURS_WITH = "co_occurs_with"
    STATE_CHANGE = "state_change"
    REPEATED_ACTIVITY = "repeated_activity"


class ScopeFilter(str, Enum):
    SAME = "SAME"
    DIFFERENT = "DIFFERENT"
    ANY = "ANY"


@dataclass
class RelationshipRule:
    """Defines a deterministic template for establishing a relationship between two events."""
    rule_id: str
    name: str
    event_type_a: str
    event_type_b: str
    relationship_type: RelationshipType
    max_time_window_seconds: float
    min_time_window_seconds: float = 0.0
    camera_scope: ScopeFilter = ScopeFilter.SAME
    zone_scope: ScopeFilter = ScopeFilter.ANY
    confidence_weight: float = 1.0


@dataclass
class EventRelationship:
    """An established concrete relationship between two concrete events."""
    relationship_id: str
    relationship_type: str
    event_a_id: str
    event_b_id: str
    time_delta_seconds: float
    confidence: float
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
