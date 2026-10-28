"""
Smart Spectator - Authentication & RBAC Module
"""

from .roles import Role, ROLE_HIERARCHY, ROLE_PERMISSIONS, has_permission, role_has_minimum_level
from .models import Principal, PrincipalType, TokenPayload, TokenResponse, LoginRequest, UserCreateRequest, UserResponse
from .passwords import hash_password, verify_password
from .tokens import create_access_token, verify_access_token, revoke_token, is_token_revoked
from .user_manager import user_manager
from .dependencies import (
    get_current_principal,
    require_role,
    require_admin,
    require_operator,
    require_viewer,
    require_device,
    get_current_device,
)

__all__ = [
    "Role",
    "ROLE_HIERARCHY",
    "ROLE_PERMISSIONS",
    "has_permission",
    "role_has_minimum_level",
    "Principal",
    "PrincipalType",
    "TokenPayload",
    "TokenResponse",
    "LoginRequest",
    "UserCreateRequest",
    "UserResponse",
    "hash_password",
    "verify_password",
    "create_access_token",
    "verify_access_token",
    "revoke_token",
    "is_token_revoked",
    "user_manager",
    "get_current_principal",
    "require_role",
    "require_admin",
    "require_operator",
    "require_viewer",
    "require_device",
    "get_current_device",
]
