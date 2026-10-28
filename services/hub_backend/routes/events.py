"""
Smart Spectator - REST API: Events Management & History
Conforms to Sections 19 & 20 of Phase 4 specification.
"""

from datetime import datetime, timezone
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends, status
from pydantic import BaseModel

from shared.schemas.v1.models import Event, EventStatus, EventSeverity
from services.hub_backend.database.connection import db_session
from services.event_engine import event_engine
from services.event_engine.state_machine import InvalidStateTransitionError
from ..auth.dependencies import require_operator, require_viewer
from ..auth.models import Principal

router = APIRouter(prefix="/events", tags=["Events"])


def _row_to_event_dict(r: Dict[str, Any]) -> Dict[str, Any]:
    meta = r.get("metadata")
    if meta is None:
        meta = json.loads(r["metadata_json"]) if r.get("metadata_json") else {}
    tracks = r.get("involved_track_ids")
    if isinstance(tracks, str):
        tracks = json.loads(tracks) if tracks else []
    elif tracks is None:
        tracks = []

    def format_dt(dt):
        return dt.isoformat() if isinstance(dt, datetime) else dt

    sev = r["severity"]
    if hasattr(sev, "value"):
        sev = sev.value

    stat = r.get("status", "detected")
    if hasattr(stat, "value"):
        stat = stat.value

    priority = r.get("priority", "MEDIUM")
    if hasattr(priority, "value"):
        priority = priority.value

    milestones = []
    if r.get("timeline_milestones_json"):
        try:
            milestones = json.loads(r["timeline_milestones_json"])
        except Exception:
            milestones = []

    # If timeline milestones are missing, synthesize from real timestamps
    if not milestones:
        try:
            from services.event_engine.timeline import build_event_timeline
            ts = r["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            st = r.get("start_time")
            if isinstance(st, str):
                st = datetime.fromisoformat(st)
            et = r.get("end_time")
            if isinstance(et, str):
                et = datetime.fromisoformat(et)
            milestones = build_event_timeline(
                event_type=r["event_type"],
                timestamp=ts,
                start_time=st,
                end_time=et,
                affected_tracks=tracks,
                has_recording=bool(r.get("recording_id")),
                metadata=meta,
            )
        except Exception:
            milestones = []

    return {
        "event_id": r["event_id"],
        "camera_id": r["camera_id"],
        "task_id": r.get("task_id"),
        "recording_id": r.get("recording_id"),
        "event_type": r["event_type"],
        "status": stat,
        "severity": sev,
        "priority": priority,
        "confidence": r["confidence"],
        "summary": r["summary"],
        "timestamp": format_dt(r["timestamp"]),
        "start_time": format_dt(r.get("start_time")),
        "end_time": format_dt(r.get("end_time")),
        "created_at": format_dt(r.get("created_at")),
        "updated_at": format_dt(r.get("updated_at")),
        "involved_track_ids": tracks,
        "zone_id": r.get("zone_id"),
        "rule_id": r.get("rule_id"),
        "explanation": r.get("explanation"),
        "timeline_milestones": milestones,
        "metadata": meta,
    }


@router.get("/stats", response_model=Dict[str, Any])
def get_event_stats(viewer: Principal = Depends(require_viewer)) -> Dict[str, Any]:
    """Retrieves operational summary statistics for events."""
    from services.hub_backend.database.repositories.event_repo import event_repository
    return event_repository.get_stats()


@router.get("", response_model=List[Dict[str, Any]])
def list_events(
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    has_recording: Optional[bool] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    sort_by: str = Query("timestamp"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    viewer: Principal = Depends(require_viewer),
):
    """Lists confirmed events with advanced filtering, sorting, and bounded pagination."""
    query = "SELECT * FROM events WHERE 1=1"
    params = []

    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if severity:
        query += " AND severity = ?"
        params.append(severity.lower())
    if priority:
        query += " AND priority = ?"
        params.append(priority.upper())
    if status:
        query += " AND status = ?"
        params.append(status.lower())
    if zone_id:
        query += " AND zone_id = ?"
        params.append(zone_id)
    if min_confidence is not None:
        query += " AND confidence >= ?"
        params.append(min_confidence)
    if has_recording is not None:
        if has_recording:
            query += " AND recording_id IS NOT NULL"
        else:
            query += " AND recording_id IS NULL"
    if start_time:
        query += " AND timestamp >= ?"
        params.append(start_time.isoformat())
    if end_time:
        query += " AND timestamp <= ?"
        params.append(end_time.isoformat())

    # Sorting
    valid_sort_cols = {"timestamp": "timestamp", "confidence": "confidence", "priority": "priority"}
    order_col = valid_sort_cols.get(sort_by.lower(), "timestamp")
    order_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

    query += f" ORDER BY {order_col} {order_dir} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with db_session() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_event_dict(r) for r in rows]


@router.get("/{event_id}", response_model=Dict[str, Any])
def get_event(event_id: str, viewer: Principal = Depends(require_viewer)):
    """Fetches full details for a single event."""
    from services.hub_backend.database.repositories.event_repo import event_repository
    row = event_repository.get_by_id(event_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    return _row_to_event_dict(row)


@router.get("/{event_id}/predictions", response_model=List[Dict[str, Any]])
def get_event_predictions(
    event_id: str,
    limit: int = Query(20, ge=1, le=50),
    viewer: Principal = Depends(require_viewer)
):
    """Fetches raw temporal model predictions correlated with this event."""
    with db_session() as conn:
        cursor = conn.execute("SELECT camera_id, timestamp, start_time, end_time FROM events WHERE event_id = ?", (event_id,))
        ev = cursor.fetchone()
        if not ev:
            raise HTTPException(status_code=404, detail="Event not found.")

        t_start = ev.get("start_time") or ev["timestamp"]
        t_end = ev.get("end_time") or ev["timestamp"]

        p_cursor = conn.execute(
            """
            SELECT * FROM event_predictions
            WHERE camera_id = ? AND timestamp >= datetime(?, '-10 seconds')
            AND timestamp <= datetime(?, '+10 seconds')
            ORDER BY timestamp ASC LIMIT ?
            """,
            (ev["camera_id"], t_start, t_end, limit),
        )
        preds = p_cursor.fetchall()
        return [
            {
                "prediction_id": p["prediction_id"],
                "camera_id": p["camera_id"],
                "timestamp": p["timestamp"],
                "event_type": p["event_type"],
                "confidence": p["confidence"],
                "affected_tracks": json.loads(p["affected_tracks"]) if p.get("affected_tracks") else [],
                "model_version": p.get("model_version"),
                "metadata": json.loads(p["metadata_json"]) if p.get("metadata_json") else {},
            }
            for p in preds
        ]


@router.post("/{event_id}/acknowledge", response_model=Dict[str, Any])
def acknowledge_event(event_id: str, operator: Principal = Depends(require_operator)):
    """Marks an event acknowledged by the user."""
    try:
        ev = event_engine.acknowledge_event(event_id)
        return _row_to_event_dict(ev.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{event_id}/dismiss", response_model=Dict[str, Any])
def dismiss_event(event_id: str, operator: Principal = Depends(require_operator)):
    """Dismisses an event with state machine validation."""
    try:
        ev = event_engine.dismiss_event(event_id)
        return _row_to_event_dict(ev.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{event_id}/resolve", response_model=Dict[str, Any])
def resolve_event(event_id: str, operator: Principal = Depends(require_operator)):
    """Manually resolves an active event."""
    try:
        ev = event_engine.resolve_event(event_id)
        return _row_to_event_dict(ev.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
