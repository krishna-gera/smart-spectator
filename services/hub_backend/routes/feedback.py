"""
Smart Spectator - Human Feedback & Drift API Route
Conforms to Sections 24 & 25 of Phase 10 Specification.
Allows operators to submit validation ratings and tracks model accuracy/drift.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, status, Depends

from ai.monitoring import feedback_manager, drift_monitor
from ..auth.dependencies import require_operator
from ..auth.models import Principal

router = APIRouter(prefix="/feedback", tags=["Human Feedback & Model Drift"])


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: Dict[str, Any] = Body(...),
    operator: Principal = Depends(require_operator),
):
    """Submits operator validation rating for an event (CORRECT, INCORRECT, NOT_SURE)."""
    event_id = payload.get("event_id")
    rating = payload.get("feedback")
    if not event_id or not rating:
        raise HTTPException(status_code=400, detail="Fields 'event_id' and 'feedback' are required.")

    notes = payload.get("notes")
    model_version = payload.get("model_version", "spectatornet_v1_int8")
    operator_id = operator.username

    try:
        return feedback_manager.record_feedback(
            event_id=event_id,
            feedback=rating,
            notes=notes,
            model_version=model_version,
            operator_id=operator_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[Dict[str, Any]])
def list_feedback(
    event_id: Optional[str] = Query(None),
    rating: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Lists operator feedback records."""
    return feedback_manager.list_feedback(event_id=event_id, rating=rating, limit=limit)


@router.get("/summary", response_model=Dict[str, Any])
def get_feedback_summary():
    """Retrieves aggregated operator validation accuracy metrics."""
    return feedback_manager.get_accuracy_summary()


@router.get("/drift", response_model=Dict[str, Any])
def check_model_drift(
    model_id: str = Query("spectatornet_v1_int8"),
    window_hours: int = Query(24, ge=1, le=168),
):
    """Evaluates recent model confidence distribution for statistical drift."""
    res = drift_monitor.check_drift(model_id=model_id, window_hours=window_hours, persist=True)
    return res.to_dict()
