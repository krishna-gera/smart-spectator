"""
Smart Spectator - Device Management & Pairing Routes
Implements docs/06_DEVICE_AUTHENTICATION.md and docs/07_API_SPECIFICATION.md
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, Field

from services.device_manager.manager import device_manager
from ..database.connection import db_session

router = APIRouter(prefix="/devices", tags=["Devices & Pairing"])


class PairingRequestBody(BaseModel):
    device_id: str = Field(..., description="Unique node hardware UUID")
    device_name: str = Field(..., description="Human-readable device label")
    device_model: Optional[str] = Field(None, description="e.g. Pixel 7 Pro")
    os_version: Optional[str] = Field(None, description="e.g. Android 14")
    app_version: Optional[str] = Field(None, description="e.g. 1.0.0")


class PairingVerifyBody(BaseModel):
    device_id: str
    verification_code: str = Field(..., description="6-digit numeric verification code")


@router.post("/pair/request", status_code=status.HTTP_202_ACCEPTED)
def request_pairing(body: PairingRequestBody, request: Request):
    """
    Step 1 of pairing: Node presents its identity and requests a 6-digit verification PIN.
    """
    client_ip = request.client.host if request.client else None
    result = device_manager.request_pairing(
        device_id=body.device_id,
        device_name=body.device_name,
        device_model=body.device_model,
        ip_address=client_ip
    )
    return result


@router.post("/pair/verify", status_code=status.HTTP_200_OK)
def verify_pairing(body: PairingVerifyBody):
    """
    Step 2 of pairing: Node or operator submits 6-digit verification PIN to complete pairing.
    """
    result = device_manager.verify_pairing(
        device_id=body.device_id,
        submitted_pin=body.verification_code
    )
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Verification failed")
        )
    return result


@router.get("", status_code=status.HTTP_200_OK)
def list_devices():
    """Returns list of registered devices and their connectivity states."""
    return device_manager.list_devices()


@router.get("/pairing/pending", status_code=status.HTTP_200_OK)
def list_pending_pairing_requests():
    """Desktop Hub utility: returns pending PINs to display on Desktop UI."""
    with db_session() as conn:
        cur = conn.execute("SELECT device_id, device_name, device_model, verification_pin, expires_at FROM pairing_requests WHERE expires_at > CURRENT_TIMESTAMP")
        return cur.fetchall()


@router.get("/{device_id}", status_code=status.HTTP_200_OK)
def get_device(device_id: str):
    """Fetches single device details."""
    with db_session() as conn:
        cur = conn.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        # Never leak auth token hash
        dev.pop("auth_token_hash", None)
        return dev


@router.delete("/{device_id}", status_code=status.HTTP_200_OK)
def revoke_device(device_id: str):
    """Instantly revokes authentication for a device."""
    revoked = device_manager.revoke_device(device_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return {"status": "revoked", "device_id": device_id}
