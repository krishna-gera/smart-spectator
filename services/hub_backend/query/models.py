"""
Smart Spectator - Query Engine Models
Conforms to Sections 12 & 13 of Phase 10 Specification.
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional


@dataclass
class StructuredQuery:
    """Validated structured query object. Never accepts raw SQL."""
    event_type: Optional[str] = None
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    priority: Optional[str] = None  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    after: Optional[str] = None  # ISO datetime or time (e.g. "22:00" or "2026-09-30T10:00:00")
    before: Optional[str] = None
    limit: int = 50
    offset: int = 0
    has_recording: Optional[bool] = None
    is_anomaly: bool = False
    raw_query_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
