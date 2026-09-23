"""Secure device pairing API — QR code + expiring codes."""
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import qrcode
import qrcode.image.svg
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.models import CameraDevice, DevicePair, DeviceType, PairingCode, PairingStatus, ViewerDevice, Device, User
from app.security.jwt import get_current_user

log = structlog.get_logger(__name__)
router = APIRouter()

PAIRING_CODE_LENGTH = 8
PAIRING_CODE_TTL_MINUTES = 10
PAIRING_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_pairing_code() -> str:
    """Generate a cryptographically random pairing code."""
    return "".join(secrets.choice(PAIRING_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))


def format_pairing_code(code: str) -> str:
    """Format as XXXX-XXXX."""
    return f"{code[:4]}-{code[4:]}"


class CreatePairingCodeResponse(BaseModel):
    pairing_code_id: str
    code: str
    formatted_code: str
    expires_at: str
    expires_in_seconds: int


class JoinPairingRequest(BaseModel):
    code: str  # The 8-char or XXXX-XXXX formatted code
    viewer_device_id: str


class JoinPairingResponse(BaseModel):
    pair_id: str
    camera_id: str
    camera_name: str
    status: str


@router.post("/create", response_model=CreatePairingCodeResponse)
async def create_pairing_code(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new pairing code for a camera device (CAM_CODER only)."""
    # Verify camera ownership
    result = await db.execute(
        select(CameraDevice).where(
            CameraDevice.id == camera_id,
            CameraDevice.user_id == current_user.id,
        )
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    # Expire any existing unused codes for this camera
    existing = await db.execute(
        select(PairingCode).where(
            PairingCode.camera_device_id == camera.id,
            PairingCode.is_used == False,
        )
    )
    for old_code in existing.scalars().all():
        old_code.is_used = True
        old_code.used_at = datetime.now(timezone.utc)

    # Generate new code
    raw_code = generate_pairing_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PAIRING_CODE_TTL_MINUTES)

    # QR data includes a deep-link style payload
    qr_data = f"smartspectator://pair?code={raw_code}&camera={camera_id}"

    pairing_code = PairingCode(
        camera_device_id=camera.id,
        code=raw_code,
        qr_data=qr_data,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(pairing_code)
    await db.commit()
    await db.refresh(pairing_code)

    log.info("Pairing code created", camera_id=camera_id, code_id=str(pairing_code.id))

    return CreatePairingCodeResponse(
        pairing_code_id=str(pairing_code.id),
        code=raw_code,
        formatted_code=format_pairing_code(raw_code),
        expires_at=expires_at.isoformat(),
        expires_in_seconds=PAIRING_CODE_TTL_MINUTES * 60,
    )


@router.get("/qr/{pairing_code_id}")
async def get_pairing_qr(
    pairing_code_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a QR code SVG image for the pairing code."""
    result = await db.execute(
        select(PairingCode).where(PairingCode.id == pairing_code_id, PairingCode.is_used == False)
    )
    code_obj = result.scalar_one_or_none()
    if not code_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing code not found or expired")

    if datetime.now(timezone.utc) > code_obj.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Pairing code expired")

    img = qrcode.make(code_obj.qr_data, image_factory=qrcode.image.svg.SvgImage)
    import io
    buffer = io.BytesIO()
    img.save(buffer)
    return Response(content=buffer.getvalue(), media_type="image/svg+xml")


@router.post("/join", response_model=JoinPairingResponse)
async def join_pairing(
    request: JoinPairingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Use a pairing code to connect a viewer device to a camera."""
    # Normalize code (remove dashes, uppercase)
    clean_code = request.code.replace("-", "").upper().strip()

    result = await db.execute(
        select(PairingCode).where(
            PairingCode.code == clean_code,
            PairingCode.is_used == False,
        )
    )
    code_obj = result.scalar_one_or_none()

    if not code_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid pairing code")

    if datetime.now(timezone.utc) > code_obj.expires_at.replace(tzinfo=timezone.utc):
        code_obj.is_used = True
        await db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Pairing code expired")

    # Verify viewer device belongs to current user
    vw_result = await db.execute(
        select(ViewerDevice).where(ViewerDevice.id == request.viewer_device_id)
    )
    viewer = vw_result.scalar_one_or_none()
    if not viewer or str(viewer.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewer device not authorized")

    # Check not already paired
    existing_pair = await db.execute(
        select(DevicePair).where(
            DevicePair.camera_id == code_obj.camera_device_id,
            DevicePair.viewer_device_id == viewer.id,
            DevicePair.status == PairingStatus.ACTIVE,
        )
    )
    if existing_pair.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already paired")

    # Mark code as used
    code_obj.is_used = True
    code_obj.used_at = datetime.now(timezone.utc)
    code_obj.used_by_device_id = viewer.id

    # Create pair
    pair = DevicePair(
        camera_id=code_obj.camera_device_id,
        viewer_device_id=viewer.id,
        status=PairingStatus.ACTIVE,
    )
    db.add(pair)
    await db.flush()

    # Get camera info
    cam_result = await db.execute(select(CameraDevice).where(CameraDevice.id == code_obj.camera_device_id))
    camera = cam_result.scalar_one()

    await db.commit()
    log.info("Devices paired", camera_id=str(camera.id), viewer_id=str(viewer.id))

    return JoinPairingResponse(
        pair_id=str(pair.id),
        camera_id=str(camera.id),
        camera_name=camera.name,
        status=pair.status.value,
    )


@router.delete("/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_pairing(
    pair_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a device pairing."""
    result = await db.execute(select(DevicePair).where(DevicePair.id == pair_id))
    pair = result.scalar_one_or_none()
    if not pair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing not found")

    # Verify ownership (camera owner or viewer owner)
    cam_result = await db.execute(select(CameraDevice).where(CameraDevice.id == pair.camera_id))
    camera = cam_result.scalar_one_or_none()
    vw_result = await db.execute(select(ViewerDevice).where(ViewerDevice.id == pair.viewer_device_id))
    viewer = vw_result.scalar_one_or_none()

    if not camera or not viewer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pairing not found")

    user_id_str = str(current_user.id)
    if str(camera.user_id) != user_id_str and str(viewer.user_id) != user_id_str:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    pair.status = PairingStatus.REVOKED
    pair.revoked_at = datetime.now(timezone.utc)
    await db.commit()
