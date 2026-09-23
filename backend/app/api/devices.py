"""Device registration and management API."""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database.session import get_db
from app.models.models import CameraDevice, Device, DevicePlatform, DeviceType, User, ViewerDevice
from app.security.jwt import get_current_user

log = structlog.get_logger(__name__)
router = APIRouter()


class RegisterDeviceRequest(BaseModel):
    device_name: str
    device_type: DeviceType
    platform: DevicePlatform
    push_token: Optional[str] = None
    app_version: Optional[str] = None
    os_version: Optional[str] = None
    device_model: Optional[str] = None


class CameraConfigRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    camera_resolution: Optional[str] = None
    analysis_interval: Optional[int] = None
    privacy_mode: Optional[bool] = None


class DeviceResponse(BaseModel):
    id: str
    device_name: str
    device_type: str
    platform: str
    is_active: bool
    camera_id: Optional[str] = None
    viewer_id: Optional[str] = None


class CameraStatusResponse(BaseModel):
    camera_id: str
    name: str
    is_online: bool
    is_monitoring: bool
    battery_level: Optional[int]
    network_type: Optional[str]
    camera_resolution: Optional[str]
    analysis_interval: int
    privacy_mode: bool
    last_heartbeat_at: Optional[str]


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    request: RegisterDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new device for the authenticated user."""
    device = Device(
        user_id=current_user.id,
        device_name=request.device_name,
        device_type=request.device_type,
        platform=request.platform,
        push_token=request.push_token,
        app_version=request.app_version,
        os_version=request.os_version,
        device_model=request.device_model,
        is_active=True,
    )
    db.add(device)
    await db.flush()

    camera_id = None
    viewer_id = None

    if request.device_type == DeviceType.CAMERA:
        camera = CameraDevice(
            device_id=device.id,
            user_id=current_user.id,
            name=f"{request.device_name} Camera",
        )
        db.add(camera)
        await db.flush()
        camera_id = str(camera.id)
    elif request.device_type == DeviceType.VIEWER:
        viewer = ViewerDevice(
            device_id=device.id,
            user_id=current_user.id,
        )
        db.add(viewer)
        await db.flush()
        viewer_id = str(viewer.id)

    await db.commit()
    log.info("Device registered", device_id=str(device.id), type=request.device_type)

    return DeviceResponse(
        id=str(device.id),
        device_name=device.device_name,
        device_type=device.device_type.value,
        platform=device.platform.value,
        is_active=device.is_active,
        camera_id=camera_id,
        viewer_id=viewer_id,
    )


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all devices for the authenticated user."""
    result = await db.execute(
        select(Device).where(Device.user_id == current_user.id, Device.is_active == True)
    )
    devices = result.scalars().all()

    response = []
    for d in devices:
        cam_result = await db.execute(select(CameraDevice).where(CameraDevice.device_id == d.id))
        cam = cam_result.scalar_one_or_none()
        vw_result = await db.execute(select(ViewerDevice).where(ViewerDevice.device_id == d.id))
        vw = vw_result.scalar_one_or_none()
        response.append(DeviceResponse(
            id=str(d.id),
            device_name=d.device_name,
            device_type=d.device_type.value,
            platform=d.platform.value,
            is_active=d.is_active,
            camera_id=str(cam.id) if cam else None,
            viewer_id=str(vw.id) if vw else None,
        ))
    return response


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a device (soft delete)."""
    result = await db.execute(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    device.is_active = False
    await db.commit()


@router.get("/cameras", response_model=List[CameraStatusResponse])
async def list_cameras(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all camera devices for the authenticated user."""
    result = await db.execute(
        select(CameraDevice).where(CameraDevice.user_id == current_user.id)
    )
    cameras = result.scalars().all()
    return [
        CameraStatusResponse(
            camera_id=str(c.id),
            name=c.name,
            is_online=c.is_online,
            is_monitoring=c.is_monitoring,
            battery_level=c.battery_level,
            network_type=c.network_type,
            camera_resolution=c.camera_resolution,
            analysis_interval=c.analysis_interval,
            privacy_mode=c.privacy_mode,
            last_heartbeat_at=c.last_heartbeat_at.isoformat() if c.last_heartbeat_at else None,
        )
        for c in cameras
    ]


@router.get("/cameras/{camera_id}/status", response_model=CameraStatusResponse)
async def get_camera_status(
    camera_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get real-time status for a specific camera."""
    result = await db.execute(
        select(CameraDevice).where(CameraDevice.id == camera_id, CameraDevice.user_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    return CameraStatusResponse(
        camera_id=str(camera.id),
        name=camera.name,
        is_online=camera.is_online,
        is_monitoring=camera.is_monitoring,
        battery_level=camera.battery_level,
        network_type=camera.network_type,
        camera_resolution=camera.camera_resolution,
        analysis_interval=camera.analysis_interval,
        privacy_mode=camera.privacy_mode,
        last_heartbeat_at=camera.last_heartbeat_at.isoformat() if camera.last_heartbeat_at else None,
    )


@router.patch("/cameras/{camera_id}")
async def configure_camera(
    camera_id: str,
    request: CameraConfigRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update camera configuration."""
    result = await db.execute(
        select(CameraDevice).where(CameraDevice.id == camera_id, CameraDevice.user_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if request.name is not None:
        camera.name = request.name
    if request.description is not None:
        camera.description = request.description
    if request.camera_resolution is not None:
        camera.camera_resolution = request.camera_resolution
    if request.analysis_interval is not None:
        camera.analysis_interval = max(1, min(60, request.analysis_interval))
    if request.privacy_mode is not None:
        camera.privacy_mode = request.privacy_mode

    await db.commit()
    return {"status": "updated"}
