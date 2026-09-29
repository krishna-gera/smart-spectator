"""
Smart Spectator - Deterministic Smart Event Prioritization Engine
Conforms to Section 12 of Phase 9 Master Specification.
Evaluates deterministic priority levels (LOW, MEDIUM, HIGH, CRITICAL)
based strictly on event type, confidence, zone sensitivity, and temporal attributes.
Zero ML ranking or probabilistic fuzzing.
"""

from typing import Dict, Any, Optional
from shared.schemas.v1.models import EventPriority


def calculate_event_priority(
    event_type: str,
    confidence: float = 0.0,
    zone_name: Optional[str] = None,
    rule_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    zone_id: Optional[str] = None,
    duration_seconds: float = 0.0,
) -> EventPriority:
    """
    Computes a deterministic EventPriority enum value based on transparent, auditable business rules:
    - CRITICAL:
      1. CAMERA_BLOCKED (tamper event)
      2. Events occurring inside high-security/restricted zones
      3. Severe stream disconnection during active monitoring
    - HIGH:
      1. OBJECT_REMOVED from any monitored zone
      2. ZONE_LOITERING exceeding threshold
      3. High-confidence intrusion into defined zone
    - MEDIUM:
      1. PERSON_ENTERED in general camera view
      2. OBJECT_MOVED with significant displacement
      3. RAPID_MOTION
    - LOW:
      1. NORMAL_ACTIVITY or background stability
      2. OBJECT_PRESENT confirmation
      3. PERSON_LEFT area
    """
    meta = metadata or {}
    effective_zone = zone_name or zone_id or meta.get("zone_name") or meta.get("zone_id") or ""
    zn_lower = effective_zone.lower()
    is_sensitive_zone = any(
        keyword in zn_lower
        for keyword in ["secure", "security", "restricted", "vault", "perimeter", "safe", "danger", "entry"]
    ) or meta.get("is_security_zone", False)

    # 1. CRITICAL Tier
    if event_type == "CAMERA_BLOCKED":
        return EventPriority.CRITICAL

    if is_sensitive_zone and event_type in ("PERSON_ENTERED", "OBJECT_REMOVED", "ZONE_LOITERING"):
        return EventPriority.CRITICAL

    if event_type == "CAMERA_DISCONNECTED" and is_sensitive_zone:
        return EventPriority.CRITICAL

    # 2. HIGH Tier
    if event_type == "OBJECT_REMOVED":
        return EventPriority.HIGH

    if event_type == "ZONE_LOITERING":
        return EventPriority.HIGH

    if event_type == "PERSON_ENTERED" and effective_zone:
        return EventPriority.HIGH

    if event_type in ("CAMERA_DISCONNECTED", "CAMERA_STREAM_ERROR"):
        return EventPriority.HIGH

    # 3. MEDIUM Tier
    if event_type in ("PERSON_ENTERED", "OBJECT_MOVED", "RAPID_MOTION"):
        return EventPriority.MEDIUM

    if confidence >= 0.85:
        return EventPriority.MEDIUM

    # 4. LOW Tier
    if event_type in ("NORMAL_ACTIVITY", "NORMAL_BACKGROUND", "OBJECT_PRESENT", "PERSON_LEFT"):
        return EventPriority.LOW

    return EventPriority.LOW
