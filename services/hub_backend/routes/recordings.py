"""
Smart Spectator - REST API: Local Recordings & Secure Media Streaming
Conforms to Sections 26, 43, 63, 64 of Phase 4 & Phase 5 specifications.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from services.hub_backend.database.connection import db_session
from services.event_engine import event_engine

router = APIRouter(prefix="/recordings", tags=["Recordings"])


def _row_to_recording_dict(r: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "recording_id": r["recording_id"],
        "camera_id": r["camera_id"],
        "event_id": r.get("event_id"),
        "file_path": Path(r["file_path"]).name,  # Mask full filesystem path for security
        "has_thumbnail": bool(r.get("thumbnail_path") and Path(r["thumbnail_path"]).exists()),
        "start_time": r["start_time"],
        "end_time": r["end_time"],
        "duration_seconds": r["duration_seconds"],
        "file_size_bytes": r["file_size_bytes"],
        "codec": r.get("codec", "h264"),
        "width": r["width"],
        "height": r["height"],
        "fps": r["fps"],
        "metadata": json.loads(r["metadata_json"]) if r.get("metadata_json") else {},
        "created_at": r["created_at"],
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_recordings(
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Lists local event recordings with pagination."""
    query = "SELECT * FROM recordings WHERE 1=1"
    params = []

    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with db_session() as conn:
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        return [_row_to_recording_dict(r) for r in rows]


@router.get("/{recording_id}", response_model=Dict[str, Any])
def get_recording(recording_id: str):
    """Retrieves recording metadata."""
    with db_session() as conn:
        cursor = conn.execute("SELECT * FROM recordings WHERE recording_id = ?", (recording_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recording not found.")
        return _row_to_recording_dict(row)


@router.get("/{recording_id}/stream")
def stream_recording(recording_id: str):
    """
    Safely streams MP4 video clip to client.
    Guarantees path traversal prevention (Section 64).
    """
    safe_path = event_engine.recording_mgr.resolve_safe_recording_path(recording_id)
    if not safe_path:
        raise HTTPException(status_code=404, detail="Recording media file not found or inaccessible.")

    return FileResponse(
        path=safe_path,
        media_type="video/mp4",
        filename=safe_path.name,
    )


@router.get("/{recording_id}/thumbnail")
def get_recording_thumbnail(recording_id: str):
    """Safely serves snapshot thumbnail for recording."""
    with db_session() as conn:
        cursor = conn.execute("SELECT thumbnail_path FROM recordings WHERE recording_id = ?", (recording_id,))
        row = cursor.fetchone()
        if not row or not row.get("thumbnail_path"):
            raise HTTPException(status_code=404, detail="Thumbnail not found.")

    thumb_p = Path(row["thumbnail_path"]).resolve()
    base_p = event_engine.recording_mgr.snapshots_dir.resolve()

    try:
        thumb_p.relative_to(base_p)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied.")

    if not thumb_p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found.")

    return FileResponse(path=thumb_p, media_type="image/jpeg")


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording(recording_id: str):
    """Deletes a recording and its underlying media file."""
    with db_session() as conn:
        cursor = conn.execute("SELECT file_path, thumbnail_path FROM recordings WHERE recording_id = ?", (recording_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recording not found.")

        # Unlink file from database
        conn.execute("DELETE FROM recordings WHERE recording_id = ?", (recording_id,))
        conn.execute("UPDATE events SET recording_id = NULL WHERE recording_id = ?", (recording_id,))

    # Safely delete disk files
    try:
        p = Path(row["file_path"])
        if p.exists():
            p.unlink()
    except Exception:
        pass
    try:
        if row.get("thumbnail_path"):
            th = Path(row["thumbnail_path"])
            if th.exists():
                th.unlink()
    except Exception:
        pass
