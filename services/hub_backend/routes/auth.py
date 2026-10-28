"""
Smart Spectator - Authentication & User Management Routes
Provides login, logout, identity inspection, and user administration endpoints.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Header, status

from ..config import settings
from ..auth.models import LoginRequest, TokenResponse, Principal, UserCreateRequest, UserResponse
from ..auth.roles import Role
from ..auth.tokens import create_access_token, revoke_token
from ..auth.user_manager import user_manager
from ..auth.dependencies import get_current_principal, require_admin

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(body: LoginRequest):
    """
    Authenticates operator or administrator credentials.
    Issues a cryptographically signed HMAC-SHA256 session token.
    """
    principal = user_manager.authenticate_user(body.username, body.password)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(
        sub=principal.id,
        username=principal.username,
        role=principal.role,
        principal_type=principal.principal_type
    )

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_seconds=settings.SESSION_TOKEN_TTL_MINUTES * 60,
        role=principal.role,
        username=principal.username
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    authorization: Optional[str] = Header(None),
    principal: Principal = Depends(get_current_principal)
):
    """
    Revokes the current caller's session token and adds its JTI to the revocation list.
    """
    raw_token = None
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            raw_token = parts[1]

    if raw_token:
        revoke_token(raw_token)

    return {"status": "logged_out", "message": "Session token successfully invalidated"}


@router.get("/me", status_code=status.HTTP_200_OK)
def get_current_user_profile(principal: Principal = Depends(get_current_principal)):
    """Returns details of the currently authenticated principal."""
    return {
        "id": principal.id,
        "username": principal.username,
        "role": principal.role.value,
        "type": principal.principal_type.value,
        "device_id": principal.device_id,
        "is_active": principal.is_active
    }


@router.get("/users", status_code=status.HTTP_200_OK)
def list_system_users(admin: Principal = Depends(require_admin)):
    """Administrator-only: lists all registered user accounts."""
    return user_manager.list_users()


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_system_user(body: UserCreateRequest, admin: Principal = Depends(require_admin)):
    """Administrator-only: creates a new user account with specified RBAC role."""
    try:
        new_principal = user_manager.create_user(
            username=body.username,
            plain_password=body.password,
            role=body.role
        )
        return {
            "status": "created",
            "user_id": new_principal.id,
            "username": new_principal.username,
            "role": new_principal.role.value
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
