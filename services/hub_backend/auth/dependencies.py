"""
Smart Spectator - FastAPI Authentication & RBAC Dependencies
Supports both human operators (JWT session tokens) and camera nodes (HMAC device tokens).
"""

from typing import Optional, Dict, Any, Callable
from fastapi import Header, Query, HTTPException, status, Depends

from services.device_manager.manager import device_manager
from .models import Principal, PrincipalType
from .roles import Role, role_has_minimum_level
from .tokens import verify_access_token
from .user_manager import user_manager


async def get_current_principal(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> Principal:
    """
    Extracts and authenticates caller identity from Bearer header or query parameter.
    Authenticates:
    1. Camera devices using HMAC device tokens (`ss_tok_v1_...`)
    2. Human operators/viewers/admins using signed JWT session tokens
    """
    raw_token = None
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1]
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials. Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Path A: Camera Device Token
    if raw_token.startswith("ss_tok_v1_"):
        device = device_manager.authenticate_token(raw_token)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or revoked device token.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return Principal(
            id=device["device_id"],
            username=device.get("device_name", device["device_id"]),
            role=Role.DEVICE,
            principal_type=PrincipalType.DEVICE,
            device_id=device["device_id"],
            is_active=True
        )

    # Path B: User Session Token
    payload = verify_access_token(raw_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked session token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return Principal(
        id=payload.sub,
        username=payload.username,
        role=payload.role,
        principal_type=payload.principal_type,
        is_active=True
    )


def require_role(minimum_role: Role) -> Callable:
    """
    Dependency factory that enforces minimum role authority level.
    Raises HTTP 403 Forbidden if current principal has insufficient privileges.
    """
    async def _role_checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not role_has_minimum_level(principal.role, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: this operation requires at least '{minimum_role.value}' role (current: '{principal.role.value}')."
            )
        return principal

    return _role_checker


# Convenient role dependencies
require_admin = require_role(Role.ADMIN)
require_operator = require_role(Role.OPERATOR)
require_viewer = require_role(Role.VIEWER)
require_device = require_role(Role.DEVICE)


async def get_current_device(
    principal: Principal = Depends(require_device)
) -> Dict[str, Any]:
    """
    Backward-compatible dependency for routes expecting device dict.
    Requires DEVICE (or ADMIN) role.
    """
    if principal.principal_type == PrincipalType.DEVICE and principal.device_id:
        with device_manager.db_session() if hasattr(device_manager, "db_session") else db_session_fallback():
            dev = device_manager.get_camera_for_device(principal.device_id)
            return {"device_id": principal.device_id, "camera": dev}
    return {"device_id": principal.id}


def db_session_fallback():
    from ..database.connection import db_session
    return db_session()
