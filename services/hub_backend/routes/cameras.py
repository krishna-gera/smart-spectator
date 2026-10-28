"""
Smart Spectator - Camera Management & Stream Control Routes
Implements docs/07_API_SPECIFICATION.md
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status, Response
from pydantic import BaseModel, Field

from ..database.repositories.camera_repo import camera_repository
from ..auth.dependencies import require_viewer, require_operator

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", status_code=status.HTTP_200_OK)
def list_cameras():
    """Lists all registered cameras."""
    return camera_repository.list_all()


@router.get("/{camera_id}", status_code=status.HTTP_200_OK)
def get_camera(camera_id: str):
    """Retrieves camera configuration and active stream state."""
    cam = camera_repository.get_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return cam


class CameraUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


@router.put("/{camera_id}", status_code=status.HTTP_200_OK)
def update_camera(camera_id: str, update: CameraUpdateRequest):
    """Updates camera configuration such as display name."""
    cam = camera_repository.get_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    if update.name is not None:
        cam = camera_repository.update_name(camera_id, update.name)
    return cam


@router.post("/{camera_id}/start", status_code=status.HTTP_200_OK)
def start_camera(camera_id: str):
    """Signals camera stream session activation."""
    ok = camera_repository.update_status(camera_id, "streaming")
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return {"camera_id": camera_id, "status": "streaming"}


@router.post("/{camera_id}/stop", status_code=status.HTTP_200_OK)
def stop_camera(camera_id: str):
    """Stops camera streaming session."""
    ok = camera_repository.update_status(camera_id, "idle")
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return {"camera_id": camera_id, "status": "idle"}


@router.post("/{camera_id}/disconnect", status_code=status.HTTP_200_OK)
def disconnect_camera(camera_id: str):
    """Disconnects active camera session."""
    from services.stream_engine.server import stream_engine
    stream_engine.remove_session(camera_id)
    return {"camera_id": camera_id, "status": "disconnected"}


@router.post("/{camera_id}/reconnect", status_code=status.HTTP_200_OK)
def reconnect_camera(camera_id: str):
    """Signals camera reconnection."""
    return start_camera(camera_id)
