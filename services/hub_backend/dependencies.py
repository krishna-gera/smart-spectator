"""
Smart Spectator - FastAPI Authentication & Request Dependencies
Re-exports dependencies from the centralized auth module.
"""

from .auth.dependencies import (
    get_current_principal,
    get_current_device,
    require_role,
    require_admin,
    require_operator,
    require_viewer,
    require_device,
)
from .auth.models import Principal, PrincipalType
from .auth.roles import Role

__all__ = [
    "get_current_principal",
    "get_current_device",
    "require_role",
    "require_admin",
    "require_operator",
    "require_viewer",
    "require_device",
    "Principal",
    "PrincipalType",
    "Role",
]
