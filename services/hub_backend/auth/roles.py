"""
Smart Spectator - Role-Based Access Control (RBAC) Definitions
Conforms to Sections 11 & 12 of Master Specification.
"""

from enum import Enum
from typing import Set


class Role(str, Enum):
    """System roles ordered by authority level."""
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"
    DEVICE = "device"


# Role authority values for hierarchical comparisons
ROLE_HIERARCHY = {
    Role.VIEWER: 10,
    Role.DEVICE: 15,
    Role.OPERATOR: 20,
    Role.ADMIN: 30,
}

# Explicit permissions per role
ROLE_PERMISSIONS = {
    Role.VIEWER: {
        "streams:read",
        "events:read",
        "recordings:read",
        "devices:read",
        "cameras:read",
        "zones:read",
        "rules:read",
        "health:read",
    },
    Role.DEVICE: {
        "streams:write",
        "telemetry:write",
        "heartbeat:write",
        "health:read",
    },
    Role.OPERATOR: {
        # Inherits all viewer permissions plus operational actions
        "streams:read",
        "events:read",
        "recordings:read",
        "devices:read",
        "cameras:read",
        "zones:read",
        "rules:read",
        "health:read",
        # Operational
        "pairing:view_pending",
        "pairing:verify",
        "events:acknowledge",
        "recordings:manual_start",
        "recordings:manual_stop",
        "zones:manage",
        "rules:manage",
        "cameras:manage",
    },
    Role.ADMIN: {
        # All permissions
        "*"
    }
}


def has_permission(role: Role, required_permission: str) -> bool:
    """Checks if a given role possesses a specific permission."""
    perms = ROLE_PERMISSIONS.get(role, set())
    if "*" in perms:
        return True
    return required_permission in perms


def role_has_minimum_level(user_role: Role, required_role: Role) -> bool:
    """
    Checks if user_role meets or exceeds the required_role authority.
    Note: DEVICE role is orthogonal and must match DEVICE or be ADMIN.
    """
    if required_role == Role.DEVICE:
        return user_role in (Role.DEVICE, Role.ADMIN)
    
    if user_role == Role.ADMIN:
        return True
        
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    req_level = ROLE_HIERARCHY.get(required_role, 0)
    return user_level >= req_level
