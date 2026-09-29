"""
Smart Spectator - FastAPI Authentication & Request Dependencies
"""

from typing import Optional, Dict, Any
from fastapi import Header, Query, HTTPException, status
from ..device_manager.manager import device_manager


async def get_current_device(
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Validates Bearer token from either Authorization header or ?token query param.
    Raises HTTP 401 if missing or invalid.
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
            detail="Missing authentication credential. Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    device = device_manager.authenticate_token(raw_token)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return device
