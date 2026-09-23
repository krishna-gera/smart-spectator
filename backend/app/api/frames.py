"""
Frame upload API — receives compressed frames from camera devices.
Enqueues them for AI analysis.
"""
import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models.models import CameraDevice, Frame, FrameRetention, MonitoringSession, MonitoringTask, SessionStatus, TaskStatus, User
from app.security.jwt import get_current_user

log = structlog.get_logger(__name__)
router = APIRouter()

MAX_FRAME_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB max per frame


class FrameUploadResponse(BaseModel):
    frame_id: str
    queued_for_analysis: bool
    session_id: Optional[str]


@router.post("/upload", response_model=FrameUploadResponse)
async def upload_frame(
    camera_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    frame_data: UploadFile = File(...),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a compressed camera frame and queue it for AI analysis.
    Only JPEG/WebP accepted. Max 2MB per frame.
    """
    # Validate camera ownership
    cam_result = await db.execute(
        select(CameraDevice).where(
            CameraDevice.id == camera_id,
            CameraDevice.user_id == current_user.id,
        )
    )
    camera = cam_result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    # Validate file type
    content_type = frame_data.content_type or ""
    if content_type not in ("image/jpeg", "image/webp", "image/png"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG/WebP/PNG frames accepted")

    # Read and validate size
    raw_bytes = await frame_data.read()
    if len(raw_bytes) > MAX_FRAME_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Frame too large")

    # Determine retention policy
    retention = FrameRetention(settings.DEFAULT_FRAME_RETENTION)
    expires_at = None
    if retention == FrameRetention.SHORT:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.FRAME_SHORT_RETENTION_HOURS)
    elif retention == FrameRetention.STANDARD:
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.FRAME_STANDARD_RETENTION_DAYS)
    elif retention == FrameRetention.NONE:
        expires_at = datetime.now(timezone.utc)

    # Save frame record (storage path will be updated by storage service)
    frame = Frame(
        camera_id=camera.id,
        session_id=session_id,
        file_size_bytes=len(raw_bytes),
        width=width,
        height=height,
        format=content_type.split("/")[-1],
        retention_policy=retention,
        expires_at=expires_at,
    )
    db.add(frame)
    await db.flush()
    frame_id = str(frame.id)

    # Update session frame count
    if session_id:
        sess_result = await db.execute(select(MonitoringSession).where(MonitoringSession.id == session_id))
        session = sess_result.scalar_one_or_none()
        if session:
            session.frame_count += 1

    await db.commit()

    # Queue for AI analysis (async — don't block upload)
    if camera.is_monitoring:
        try:
            from app.workers.tasks import analyze_frame_task
            # Get active task for this camera
            task_result = await db.execute(
                select(MonitoringTask).where(
                    MonitoringTask.camera_id == camera.id,
                    MonitoringTask.status == TaskStatus.MONITORING,
                )
            )
            active_task = task_result.scalar_one_or_none()
            task_id_str = str(active_task.id) if active_task else None

            # Encode frame as base64 for Celery
            frame_b64 = base64.b64encode(raw_bytes).decode("utf-8")
            analyze_frame_task.delay(
                frame_id=frame_id,
                camera_id=str(camera.id),
                session_id=session_id,
                task_id=task_id_str,
                frame_b64=frame_b64,
                content_type=content_type,
            )
            queued = True
        except Exception as exc:
            log.error("Failed to queue frame for analysis", error=str(exc), frame_id=frame_id)
            queued = False
    else:
        queued = False

    return FrameUploadResponse(
        frame_id=frame_id,
        queued_for_analysis=queued,
        session_id=session_id,
    )


@router.post("/heartbeat")
async def camera_heartbeat(
    camera_id: str,
    battery_level: Optional[int] = None,
    network_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Camera sends a heartbeat to indicate it's online."""
    cam_result = await db.execute(
        select(CameraDevice).where(
            CameraDevice.id == camera_id,
            CameraDevice.user_id == current_user.id,
        )
    )
    camera = cam_result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera.is_online = True
    camera.last_heartbeat_at = datetime.now(timezone.utc)
    if battery_level is not None:
        camera.battery_level = max(0, min(100, battery_level))
    if network_type is not None:
        camera.network_type = network_type[:20]

    await db.commit()
    return {"status": "ok"}
