"""Monitoring tasks and sessions API."""
from datetime import datetime, timezone
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.models import (
    CameraDevice, MonitoringSession, MonitoringTask,
    MonitoringType, SessionStatus, TaskStatus, User,
)
from app.security.jwt import get_current_user

log = structlog.get_logger(__name__)
router = APIRouter()


class CreateTaskRequest(BaseModel):
    camera_id: str
    title: str
    description: Optional[str] = None
    monitoring_type: MonitoringType = MonitoringType.CUSTOM
    condition: Optional[str] = None
    target_object: Optional[str] = None
    threshold: Optional[float] = None
    analysis_interval: int = 2
    rule_config: Optional[dict] = None


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[str] = None
    target_object: Optional[str] = None
    threshold: Optional[float] = None
    analysis_interval: Optional[int] = None
    rule_config: Optional[dict] = None


class TaskResponse(BaseModel):
    id: str
    camera_id: Optional[str]
    title: str
    description: Optional[str]
    monitoring_type: str
    condition: Optional[str]
    target_object: Optional[str]
    threshold: Optional[float]
    analysis_interval: int
    status: str
    rule_config: Optional[dict]
    created_at: str
    updated_at: str


class SessionResponse(BaseModel):
    id: str
    task_id: str
    camera_id: Optional[str]
    status: str
    started_at: str
    ended_at: Optional[str]
    frame_count: int
    event_count: int


def task_to_response(task: MonitoringTask) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        camera_id=str(task.camera_id) if task.camera_id else None,
        title=task.title,
        description=task.description,
        monitoring_type=task.monitoring_type.value,
        condition=task.condition,
        target_object=task.target_object,
        threshold=task.threshold,
        analysis_interval=task.analysis_interval,
        status=task.status.value,
        rule_config=task.rule_config,
        created_at=task.created_at.isoformat() if task.created_at else "",
        updated_at=task.updated_at.isoformat() if task.updated_at else "",
    )


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: CreateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new monitoring task."""
    # Verify camera ownership
    cam_result = await db.execute(
        select(CameraDevice).where(CameraDevice.id == request.camera_id, CameraDevice.user_id == current_user.id)
    )
    camera = cam_result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if request.threshold is not None:
        request.threshold = max(0.0, min(1.0, request.threshold))

    task = MonitoringTask(
        user_id=current_user.id,
        camera_id=camera.id,
        title=request.title,
        description=request.description,
        monitoring_type=request.monitoring_type,
        condition=request.condition,
        target_object=request.target_object,
        threshold=request.threshold,
        analysis_interval=max(1, min(60, request.analysis_interval)),
        status=TaskStatus.IDLE,
        rule_config=request.rule_config,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    log.info("Monitoring task created", task_id=str(task.id))
    return task_to_response(task)


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all monitoring tasks for the authenticated user."""
    result = await db.execute(
        select(MonitoringTask).where(MonitoringTask.user_id == current_user.id)
        .order_by(MonitoringTask.created_at.desc())
    )
    return [task_to_response(t) for t in result.scalars().all()]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MonitoringTask).where(MonitoringTask.id == task_id, MonitoringTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task_to_response(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MonitoringTask).where(MonitoringTask.id == task_id, MonitoringTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status == TaskStatus.MONITORING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot update a running task")

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.condition is not None:
        task.condition = request.condition
    if request.target_object is not None:
        task.target_object = request.target_object
    if request.threshold is not None:
        task.threshold = max(0.0, min(1.0, request.threshold))
    if request.analysis_interval is not None:
        task.analysis_interval = max(1, min(60, request.analysis_interval))
    if request.rule_config is not None:
        task.rule_config = request.rule_config

    await db.commit()
    await db.refresh(task)
    return task_to_response(task)


@router.post("/tasks/{task_id}/start", response_model=SessionResponse)
async def start_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a monitoring task — creates a new monitoring session."""
    result = await db.execute(
        select(MonitoringTask).where(MonitoringTask.id == task_id, MonitoringTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status == TaskStatus.MONITORING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is already running")

    task.status = TaskStatus.MONITORING

    # Mark camera as monitoring
    if task.camera_id:
        cam_result = await db.execute(select(CameraDevice).where(CameraDevice.id == task.camera_id))
        camera = cam_result.scalar_one_or_none()
        if camera:
            camera.is_monitoring = True

    session = MonitoringSession(
        task_id=task.id,
        camera_id=task.camera_id,
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    log.info("Monitoring session started", task_id=task_id, session_id=str(session.id))

    return SessionResponse(
        id=str(session.id),
        task_id=str(session.task_id),
        camera_id=str(session.camera_id) if session.camera_id else None,
        status=session.status.value,
        started_at=session.started_at.isoformat() if session.started_at else "",
        ended_at=None,
        frame_count=session.frame_count,
        event_count=session.event_count,
    )


@router.post("/tasks/{task_id}/stop")
async def stop_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stop an active monitoring task."""
    result = await db.execute(
        select(MonitoringTask).where(MonitoringTask.id == task_id, MonitoringTask.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status != TaskStatus.MONITORING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task is not running")

    task.status = TaskStatus.IDLE

    # Close active session
    sess_result = await db.execute(
        select(MonitoringSession).where(
            MonitoringSession.task_id == task.id,
            MonitoringSession.status == SessionStatus.ACTIVE,
        )
    )
    session = sess_result.scalar_one_or_none()
    if session:
        session.status = SessionStatus.COMPLETED
        session.ended_at = datetime.now(timezone.utc)

    # Update camera
    if task.camera_id:
        cam_result = await db.execute(select(CameraDevice).where(CameraDevice.id == task.camera_id))
        camera = cam_result.scalar_one_or_none()
        if camera:
            camera.is_monitoring = False

    await db.commit()
    log.info("Monitoring stopped", task_id=task_id)
    return {"status": "stopped"}


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    task_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List monitoring sessions, optionally filtered by task."""
    query = (
        select(MonitoringSession)
        .join(MonitoringTask, MonitoringSession.task_id == MonitoringTask.id)
        .where(MonitoringTask.user_id == current_user.id)
        .order_by(MonitoringSession.started_at.desc())
    )
    if task_id:
        query = query.where(MonitoringSession.task_id == task_id)

    result = await db.execute(query)
    sessions = result.scalars().all()

    return [
        SessionResponse(
            id=str(s.id),
            task_id=str(s.task_id),
            camera_id=str(s.camera_id) if s.camera_id else None,
            status=s.status.value,
            started_at=s.started_at.isoformat() if s.started_at else "",
            ended_at=s.ended_at.isoformat() if s.ended_at else None,
            frame_count=s.frame_count,
            event_count=s.event_count,
        )
        for s in sessions
    ]
