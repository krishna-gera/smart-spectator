"""Alerts API."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.models import Alert, AlertSeverity, User
from app.security.jwt import get_current_user

router = APIRouter()


class AlertResponse(BaseModel):
    id: str
    event_id: Optional[str]
    severity: str
    title: str
    message: str
    is_read: bool
    is_dismissed: bool
    metadata: Optional[dict]
    created_at: str


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    unread_only: bool = False,
    severity: Optional[AlertSeverity] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Alert)
        .where(Alert.user_id == current_user.id, Alert.is_dismissed == False)
        .order_by(Alert.created_at.desc())
        .limit(min(limit, 200))
    )
    if unread_only:
        query = query.where(Alert.is_read == False)
    if severity:
        query = query.where(Alert.severity == severity)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertResponse(
            id=str(a.id),
            event_id=str(a.event_id) if a.event_id else None,
            severity=a.severity.value,
            title=a.title,
            message=a.message,
            is_read=a.is_read,
            is_dismissed=a.is_dismissed,
            metadata=a.metadata,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in alerts
    ]


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    is_read: Optional[bool] = None,
    is_dismissed: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if is_read is not None:
        alert.is_read = is_read
        if is_read:
            alert.read_at = datetime.now(timezone.utc)
    if is_dismissed is not None:
        alert.is_dismissed = is_dismissed

    await db.commit()
    return {"status": "updated"}
