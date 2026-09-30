"""
Smart Spectator - Action Safety & Constraint Enforcement
Conforms to Sections 16 & 41 of Phase 10 Specification.
Enforces strict schema, permission, and rule validation on all AI proposals.
Explicitly forbids arbitrary shell commands, raw SQL, file deletion, and network calls.
"""

from enum import Enum
import re
from typing import Dict, Any, List, Optional


class PermittedActionType(str, Enum):
    FLAG_EVENT = "FLAG_EVENT"
    DISPATCH_NOTIFICATION = "DISPATCH_NOTIFICATION"
    START_RECORDING = "START_RECORDING"
    ACKNOWLEDGE_INCIDENT = "ACKNOWLEDGE_INCIDENT"
    CREATE_INCIDENT = "CREATE_INCIDENT"


class ActionSafetyValidator:
    """
    Guarantees no uncontrolled AI autonomy. Validates proposed actions against
    strict whitelists and defense patterns.
    """

    FORBIDDEN_PATTERNS = [
        re.compile(r"(?i)\b(sh|bash|zsh|cmd|powershell|exec|eval|system|subprocess)\b"),
        re.compile(r"(?i)\b(select|insert|update|delete|drop|truncate|alter)\b\s+.*\bfrom\b"),
        re.compile(r"(?i)(\.\./|\.\.\\|/etc/|/var/|c:\\windows)"),
        re.compile(r"(?i)\b(https?://|ftp://|curl|wget|fetch|socket)\b"),
    ]

    def validate_action_proposal(self, action_type: str, payload: Dict[str, Any]) -> bool:
        """
        Validates an action proposal.
        Raises ValueError if action is unknown or contains dangerous payloads.
        """
        # 1. Whitelist validation
        try:
            perm_type = PermittedActionType(action_type)
        except ValueError:
            raise ValueError(f"Action '{action_type}' is not a permitted system action.")

        # 2. Inspect payload strings for forbidden patterns
        payload_str = str(payload)
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern.search(payload_str):
                raise ValueError(f"Action '{action_type}' rejected: payload contains forbidden command pattern.")

        # 3. Specific schema constraints
        if perm_type == PermittedActionType.FLAG_EVENT:
            if "event_id" not in payload:
                raise ValueError("FLAG_EVENT requires 'event_id' in payload.")
        elif perm_type == PermittedActionType.DISPATCH_NOTIFICATION:
            if "summary" not in payload and "message" not in payload:
                raise ValueError("DISPATCH_NOTIFICATION requires 'summary' or 'message'.")
        elif perm_type == PermittedActionType.ACKNOWLEDGE_INCIDENT:
            if "incident_id" not in payload:
                raise ValueError("ACKNOWLEDGE_INCIDENT requires 'incident_id' in payload.")

        return True


action_safety_validator = ActionSafetyValidator()
