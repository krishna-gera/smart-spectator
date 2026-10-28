"""
Smart Spectator - Anomalies API Route
Conforms to Sections 8, 9 & 32 of Phase 10 Specification.
Reports statistical deviations, baselines, and explanation strings.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, status, Depends

from services.event_engine.anomaly import (
    anomaly_detector,
    baseline_engine,
)
from ..auth.dependencies import require_operator
from ..auth.models import Principal

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection & Baselines"])


@router.get("", response_model=List[Dict[str, Any]])
def list_anomalies(
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Lists recent statistical anomalies detected locally."""
    reports = anomaly_detector.list_anomalies(camera_id=camera_id, limit=limit, offset=offset)
    return [r.to_dict() for r in reports]


@router.get("/baselines", response_model=List[Dict[str, Any]])
def list_baselines(camera_id: Optional[str] = Query(None)):
    """Retrieves current hourly behavioral baseline profiles."""
    from dataclasses import asdict
    profiles = baseline_engine.compute_hourly_frequency_baselines(camera_id=camera_id, persist=False)
    return [asdict(p) for p in profiles]


@router.post("/recompute-baselines", status_code=status.HTTP_200_OK)
def recompute_baselines(
    camera_id: Optional[str] = Query(None),
    operator: Principal = Depends(require_operator),
):
    """Recomputes and persists baseline metrics from historical event frequency."""
    profiles = baseline_engine.compute_hourly_frequency_baselines(camera_id=camera_id, persist=True)
    return {
        "status": "success",
        "baselines_updated": len(profiles),
        "camera_id": camera_id or "global",
    }


@router.post("/evaluate", response_model=Dict[str, Any])
def evaluate_anomaly(
    payload: Dict[str, Any] = Body(...),
    operator: Principal = Depends(require_operator),
):
    """Evaluates whether an observed event count constitutes a statistical anomaly."""
    observed = float(payload.get("observed_count", 0.0))
    hour = int(payload.get("hour_of_day", 12))
    camera_id = payload.get("camera_id")
    z_thresh = payload.get("z_threshold")
    persist = bool(payload.get("persist", True))

    report = anomaly_detector.evaluate_frequency_anomaly(
        observed_count=observed,
        hour_of_day=hour,
        camera_id=camera_id,
        z_threshold=float(z_thresh) if z_thresh else None,
        persist=persist,
    )

    if not report:
        return {
            "is_anomaly": False,
            "message": "Activity is within normal statistical baseline range.",
            "observed_count": observed,
            "hour_of_day": hour,
        }

    return {
        "is_anomaly": True,
        "report": report.to_dict(),
    }
