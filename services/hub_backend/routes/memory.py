"""
Smart Spectator - Memory & Analytics API Route
Conforms to Sections 6, 7, 10 & 33 of Phase 10 Specification.
Provides structured access to historical memory aggregations, relationships, and patterns.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body, status

from services.event_engine.memory import local_memory
from services.event_engine.patterns import pattern_engine

router = APIRouter(prefix="/memory", tags=["Local Event Memory & Analytics"])


@router.get("/daily-summary", response_model=List[Dict[str, Any]])
def get_daily_summary(days: int = Query(7, ge=1, le=90)):
    """Retrieves aggregated event counts per day for the last N days."""
    return local_memory.get_daily_activity_summary(days=days)


@router.get("/top-cameras", response_model=List[Dict[str, Any]])
def get_top_cameras(
    since_time: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20),
):
    """Ranks cameras by total generated event activity."""
    return local_memory.get_top_cameras_by_activity(since_time=since_time, limit=limit)


@router.get("/hour-window", response_model=List[Dict[str, Any]])
def get_events_in_hour_window(
    start_hour: int = Query(22, ge=0, le=23),
    end_hour: int = Query(6, ge=0, le=23),
    date_str: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Retrieves events occurring within a specific hour range (e.g., after-hours)."""
    return local_memory.get_events_in_hour_window(
        start_hour=start_hour,
        end_hour=end_hour,
        date_str=date_str,
        limit=limit,
    )


@router.get("/relationships", response_model=List[Dict[str, Any]])
def list_event_relationships(limit: int = Query(50, ge=1, le=200)):
    """Lists recent discovered causal/temporal event relationships."""
    return local_memory.get_recent_relationships(limit=limit)


@router.get("/patterns", response_model=List[Dict[str, Any]])
def list_patterns(
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Lists discovered temporal patterns."""
    patterns = pattern_engine.list_patterns(camera_id=camera_id, limit=limit)
    return [p.to_dict() for p in patterns]


@router.post("/patterns/scan", response_model=List[Dict[str, Any]])
def scan_patterns(
    camera_id: Optional[str] = Query(None),
    window_minutes: int = Query(60, ge=10, le=1440),
    min_frequency: int = Query(3, ge=2, le=20),
):
    """Triggers an on-demand scan for repeated temporal activity patterns."""
    discovered = pattern_engine.scan_for_patterns(
        camera_id=camera_id,
        window_minutes=window_minutes,
        min_frequency=min_frequency,
        persist=True,
    )
    return [p.to_dict() for p in discovered]
