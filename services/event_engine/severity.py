"""
Smart Spectator - Event Engine: Severity Determination
Derives event severity based on policy rules and event taxonomy, distinctly from model confidence.
"""

from typing import Optional, Dict
from shared.schemas.v1.models import EventSeverity


# Configurable default severity mapping per event taxonomy
DEFAULT_TAXONOMY_SEVERITY: Dict[str, EventSeverity] = {
    "NORMAL_BACKGROUND": EventSeverity.LOW,
    "OBJECT_PRESENT": EventSeverity.LOW,
    "OBJECT_REMOVED": EventSeverity.MEDIUM,
    "OBJECT_MOVED": EventSeverity.MEDIUM,
    "PERSON_ENTERED": EventSeverity.MEDIUM,
    "PERSON_LEFT": EventSeverity.LOW,
    "ZONE_LOITERING": EventSeverity.HIGH,
    "CAMERA_BLOCKED": EventSeverity.HIGH,
    "TASK_COMPLETED": EventSeverity.LOW,
    # System events
    "CAMERA_CONNECTED": EventSeverity.INFO,
    "CAMERA_DISCONNECTED": EventSeverity.HIGH,
    "CAMERA_RECONNECTED": EventSeverity.INFO,
    "CAMERA_STREAM_ERROR": EventSeverity.HIGH,
}


class SeverityCalculator:
    """
    Computes final event severity by evaluating rule overrides,
    time-of-day contextual escalation, and default taxonomic classification.
    """

    def __init__(self, overrides: Optional[Dict[str, EventSeverity]] = None):
        self._taxonomy_defaults = DEFAULT_TAXONOMY_SEVERITY.copy()
        if overrides:
            self._taxonomy_defaults.update(overrides)

    def calculate(
        self,
        event_type: str,
        confidence: float,
        rule_override: Optional[EventSeverity] = None,
        is_nighttime: bool = False,
    ) -> EventSeverity:
        """
        Derives event severity.
        Rule overrides take highest precedence.
        Confidence does NOT solely dictate danger level, but low-confidence predictions
        never escalate to CRITICAL.
        """
        if rule_override is not None:
            return rule_override

        base_sev = self._taxonomy_defaults.get(event_type, EventSeverity.MEDIUM)

        # Contextual escalation: Person entered or object moved during nighttime hours
        if is_nighttime and event_type in ("PERSON_ENTERED", "ZONE_LOITERING"):
            if base_sev == EventSeverity.MEDIUM:
                return EventSeverity.HIGH
            elif base_sev == EventSeverity.HIGH:
                return EventSeverity.CRITICAL

        # High confidence camera blockage is critical
        if event_type == "CAMERA_BLOCKED" and confidence >= 0.90:
            return EventSeverity.CRITICAL

        return base_sev
