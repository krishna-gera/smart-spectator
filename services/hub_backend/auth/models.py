"""
Smart Spectator - Authentication & Authorization Data Models
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from .roles import Role


class PrincipalType(str, Enum):
    USER = "user"
    DEVICE = "device"


class Principal(BaseModel):
    """Represents the authenticated caller (either human operator/viewer/admin or camera node)."""
    id: str
    username: str
    role: Role
    principal_type: PrincipalType = PrincipalType.USER
    device_id: Optional[str] = None
    is_active: bool = True


class TokenPayload(BaseModel):
    sub: str  # user_id or device_id
    username: str
    role: Role
    principal_type: PrincipalType
    iat: int
    exp: int
    jti: str  # unique token id for revocation


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int
    role: Role
    username: str


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    role: Role = Role.VIEWER


class UserResponse(BaseModel):
    user_id: str
    username: str
    role: Role
    is_active: bool
    created_at: str
    last_login: Optional[str] = None
