"""
Smart Spectator - Incident Models
Conforms to Section 4 of Phase 10 Specification.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
import uuid


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass
class Incident:
    incident_id: str
    incident_type: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    summary: str
    camera_ids: List[str]
    zone_ids: List[str]
    source_event_ids: List[str]
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value if isinstance(self.severity, IncidentSeverity) else self.severity
        d["status"] = self.status.value if isinstance(self.status, IncidentStatus) else self.status
        return d
