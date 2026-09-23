"""Events API."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.models import Event, MonitoringTask, User
from app.security.jwt import get_current_user

router = APIRouter()


class EventResponse(BaseModel):
    id: str
    camera_id: Optional[str]
    task_id: Optional[str]
    type: str
    confidence: Optional[float]
    description: str
    evidence_frame_id: Optional[str]
    metadata: Optional[dict]
    is_read: bool
    timestamp: str


@router.get("", response_model=List[EventResponse])
async def list_events(
    camera_id: Optional[str] = None,
    task_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Event)
        .join(MonitoringTask, Event.task_id == MonitoringTask.id, isouter=True)
        .where(MonitoringTask.user_id == current_user.id)
        .order_by(Event.timestamp.desc())
        .limit(min(limit, 200))
    )
    if camera_id:
        query = query.where(Event.camera_id == camera_id)
    if task_id:
        query = query.where(Event.task_id == task_id)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        EventResponse(
            id=str(e.id),
            camera_id=str(e.camera_id) if e.camera_id else None,
            task_id=str(e.task_id) if e.task_id else None,
            type=e.type.value,
            confidence=e.confidence,
            description=e.description,
            evidence_frame_id=str(e.evidence_frame_id) if e.evidence_frame_id else None,
            metadata=e.metadata,
            is_read=e.is_read,
            timestamp=e.timestamp.isoformat() if e.timestamp else "",
        )
        for e in events
    ]


@router.patch("/{event_id}/read")
async def mark_event_read(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.is_read = True
    await db.commit()
    return {"status": "read"}
