"""
Celery app configuration and task definitions.
AI frame analysis is handled asynchronously here.
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog
from celery import Celery

from app.core.config import settings

log = structlog.get_logger(__name__)

celery_app = Celery(
    "smart_spectator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker (vision is heavy)
    task_routes={
        "app.workers.tasks.analyze_frame_task": {"queue": "vision"},
        "app.workers.tasks.cleanup_expired_frames": {"queue": "default"},
    },
    beat_schedule={
        "cleanup-expired-frames": {
            "task": "app.workers.tasks.cleanup_expired_frames",
            "schedule": 3600.0,  # Every hour
        },
    },
)


def _run_async(coro):
    """Run an async coroutine in a new event loop (for Celery workers)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.workers.tasks.analyze_frame_task",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    time_limit=120,
    soft_time_limit=90,
)
def analyze_frame_task(
    self,
    frame_id: str,
    camera_id: str,
    session_id: Optional[str],
    task_id: Optional[str],
    frame_b64: str,
    content_type: str = "image/jpeg",
):
    """
    Celery task: analyze a camera frame using the AI pipeline.
    Stores the observation in the database and broadcasts results via WebSocket.
    """
    return _run_async(_process_frame_async(
        frame_id=frame_id,
        camera_id=camera_id,
        session_id=session_id,
        task_id=task_id,
        frame_b64=frame_b64,
        content_type=content_type,
    ))


async def _process_frame_async(
    frame_id: str,
    camera_id: str,
    session_id: Optional[str],
    task_id: Optional[str],
    frame_b64: str,
    content_type: str,
):
    from app.database.session import AsyncSessionLocal
    from app.models.models import (
        Alert, AlertSeverity, CameraDevice, Event, EventType,
        MonitoringTask, Observation, TaskStatus,
    )
    from app.services.orchestrator.orchestrator import AIOrchestrator
    from app.services.vision.base import TaskContext
    from sqlalchemy import select

    orchestrator = AIOrchestrator()

    async with AsyncSessionLocal() as db:
        # Load task context
        task_context = None
        task_config = {}
        monitoring_type = "CUSTOM"

        if task_id:
            task_result = await db.execute(select(MonitoringTask).where(MonitoringTask.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                task_context = TaskContext(
                    task_title=task.title,
                    task_description=task.description or "",
                    target_object=task.target_object,
                    threshold=task.threshold,
                    monitoring_type=task.monitoring_type.value,
                    condition=task.condition,
                )
                task_config = task.rule_config or {
                    "threshold": task.threshold or 0.8,
                    "target_object": task.target_object or "",
                    "monitoring_type": task.monitoring_type.value,
                }
                monitoring_type = task.monitoring_type.value

    # Run AI pipeline (outside DB session to avoid holding connection)
    result = await orchestrator.process_frame(
        frame_b64=frame_b64,
        camera_id=camera_id,
        session_id=session_id,
        task_id=task_id,
        task_context=task_context,
        task_config=task_config,
        monitoring_type=monitoring_type,
    )

    if result is None:
        log.error("AI pipeline returned no result", frame_id=frame_id)
        return {"status": "error", "frame_id": frame_id}

    # Save to database
    async with AsyncSessionLocal() as db:
        obs = Observation(
            session_id=session_id,
            camera_id=camera_id,
            frame_id=frame_id,
            state=result["state"],
            confidence=result["confidence"],
            objects_detected=result["objects"],
            measurements=result["measurements"],
            change_detected=result["change_detected"],
            severity=result.get("severity", "normal"),
            explanation=result.get("explanation", ""),
            raw_ai_output=result,
        )
        db.add(obs)
        await db.flush()

        # Generate event if rule triggered
        event_id = None
        if result.get("rule_triggered") and task_id:
            event = Event(
                camera_id=camera_id,
                task_id=task_id,
                session_id=session_id,
                type=EventType(result["rule_event_type"]) if result.get("rule_event_type") else EventType.STATE_CHANGED,
                confidence=result["confidence"],
                description=result.get("rule_description", result["explanation"]),
                evidence_frame_id=frame_id,
                metadata=result,
            )
            db.add(event)
            await db.flush()
            event_id = str(event.id)

            # Create alert for the user
            if task_id:
                task_result = await db.execute(select(MonitoringTask).where(MonitoringTask.id == task_id))
                task = task_result.scalar_one_or_none()
                if task:
                    severity_map = {"critical": AlertSeverity.CRITICAL, "warning": AlertSeverity.WARNING}
                    alert = Alert(
                        event_id=event.id,
                        user_id=task.user_id,
                        severity=severity_map.get(result.get("severity", "normal"), AlertSeverity.INFO),
                        title=f"Smart Spectator: {task.title}",
                        message=result.get("explanation", "Monitoring condition triggered."),
                        metadata={"camera_id": camera_id, "state": result["state"]},
                    )
                    db.add(alert)

                    # Mark task as completed if threshold reached
                    if result["rule_event_type"] in ("THRESHOLD_REACHED", "MONITORING_COMPLETED"):
                        task.status = TaskStatus.COMPLETED

        await db.commit()

    # Broadcast via WebSocket
    try:
        from app.api.websocket import manager
        ws_payload = {
            "type": "AI_RESULT",
            "camera_id": camera_id,
            "frame_id": frame_id,
            "state": result["state"],
            "confidence": result["confidence"],
            "explanation": result.get("explanation", ""),
            "measurements": result.get("measurements", {}),
            "change_detected": result.get("change_detected", False),
            "severity": result.get("severity", "normal"),
            "rule_triggered": result.get("rule_triggered", False),
            "event_id": event_id,
            "timestamp": result.get("timestamp"),
        }
        await manager.broadcast_to_camera(camera_id, ws_payload)
    except Exception as e:
        log.warning("WebSocket broadcast failed", error=str(e))

    return {"status": "ok", "frame_id": frame_id, "state": result["state"]}


@celery_app.task(name="app.workers.tasks.cleanup_expired_frames")
def cleanup_expired_frames():
    """Delete expired frames from storage and database."""
    return _run_async(_cleanup_frames_async())


async def _cleanup_frames_async():
    from app.database.session import AsyncSessionLocal
    from app.models.models import Frame
    from sqlalchemy import delete, select

    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Frame).where(Frame.expires_at <= now)
        )
        expired = result.scalars().all()
        count = len(expired)

        for frame in expired:
            await db.delete(frame)

        await db.commit()
        log.info("Expired frames cleaned up", count=count)
        return {"cleaned_up": count}
