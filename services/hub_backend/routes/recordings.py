"""
Smart Spectator - REST API: Local Recordings & Secure Media Streaming
Conforms to Sections 26, 43, 63, 64 of Phase 4 & Phase 5 specifications.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import FileResponse

from services.hub_backend.database.repositories.recording_repo import recording_repository
from services.hub_backend.database.repositories.audit_repo import audit_repository
from services.event_engine import event_engine
from ..auth.dependencies import require_admin, require_operator, require_viewer
from ..auth.models import Principal

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
        "is_locked": bool(r.get("is_locked", 0)),
        "metadata": json.loads(r["metadata_json"]) if r.get("metadata_json") else {},
        "created_at": r["created_at"],
    }


@router.get("", response_model=List[Dict[str, Any]])
def list_recordings(
    camera_id: Optional[str] = Query(None),
    event_id: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    min_size_bytes: Optional[int] = Query(None),
    is_locked: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    viewer: Principal = Depends(require_viewer),
):
    """Lists completed video recordings with filtering options."""
    rows = recording_repository.list_recordings(
        camera_id=camera_id,
        is_locked=is_locked,
        limit=limit,
        offset=offset,
    )
    return [_row_to_recording_dict(r) for r in rows]


@router.get("/{recording_id}", response_model=Dict[str, Any])
def get_recording(recording_id: str, viewer: Principal = Depends(require_viewer)):
    """Retrieves recording metadata."""
    row = recording_repository.get_by_id(recording_id)
    if not row:
        raise HTTPException(status_code=404, detail="Recording not found.")
    return _row_to_recording_dict(row)


@router.get("/{recording_id}/stream")
def stream_recording(recording_id: str, viewer: Principal = Depends(require_viewer)):
    """
    Safely streams MP4 video clip to client inline.
    Guarantees path traversal prevention (Section 64).
    """
    safe_path = event_engine.recording_mgr.resolve_safe_recording_path(recording_id)
    if not safe_path or not safe_path.exists():
        raise HTTPException(status_code=404, detail="Recording media file not found or inaccessible.")

    return FileResponse(
        path=safe_path,
        media_type="video/mp4",
        filename=safe_path.name,
    )


@router.get("/{recording_id}/download")
def download_recording(recording_id: str, viewer: Principal = Depends(require_viewer)):
    """Safely triggers attachment download of recording."""
    safe_path = event_engine.recording_mgr.resolve_safe_recording_path(recording_id)
    if not safe_path or not safe_path.exists():
        raise HTTPException(status_code=404, detail="Recording media file not found.")

    return FileResponse(
        path=safe_path,
        media_type="application/octet-stream",
        filename=safe_path.name,
        headers={"Content-Disposition": f"attachment; filename={safe_path.name}"}
    )


@router.patch("/{recording_id}/lock", response_model=Dict[str, Any])
def toggle_recording_lock(recording_id: str, operator: Principal = Depends(require_operator)):
    """Toggles retention protection lock flag on recording."""
    res = recording_repository.toggle_lock(recording_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Recording not found.")
    return {"recording_id": recording_id, "is_locked": res}


@router.get("/{recording_id}/thumbnail")
def get_recording_thumbnail(recording_id: str, viewer: Principal = Depends(require_viewer)):
    """Safely serves snapshot thumbnail for recording."""
    thumb_path = recording_repository.get_thumbnail_path(recording_id)
    if not thumb_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found.")

    thumb_p = Path(thumb_path).resolve()
    base_dir = event_engine.recording_mgr.recordings_dir.resolve()
    if base_dir not in thumb_p.parents and thumb_p.parent != base_dir:
        raise HTTPException(status_code=403, detail="Access denied.")

    if not thumb_p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found.")

    return FileResponse(path=thumb_p, media_type="image/jpeg")


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recording(recording_id: str, admin: Principal = Depends(require_admin)):
    """
    Deletes a recording and its underlying media file.
    Rejects deletion if recording is protected by retention lock.
    Requires administrator privileges.
    """
    row = recording_repository.get_by_id(recording_id)
    if not row:
        raise HTTPException(status_code=404, detail="Recording not found.")

    if row.get("is_locked"):
        raise HTTPException(
            status_code=403,
            detail="Recording is protected by retention lock. Unlock recording before deletion."
        )

    recording_repository.delete_record(recording_id)

    audit_repository.log(
        action="DELETE_RECORDING",
        actor=admin.username,
        resource=f"recording:{recording_id}",
        details={"file_name": Path(row["file_path"]).name}
    )

    # Safely delete disk files after checking base dir confinement
    try:
        p = Path(row["file_path"]).resolve()
        base_dir = event_engine.recording_mgr.recordings_dir.resolve()
        if base_dir in p.parents or p.parent == base_dir:
            if p.exists() and p.is_file():
                p.unlink()
    except Exception as e:
        print(f"[RecordingsAPI] File unlink warning: {e}")

    try:
        if row.get("thumbnail_path"):
            tp = Path(row["thumbnail_path"]).resolve()
            base_dir = event_engine.recording_mgr.recordings_dir.resolve()
            if (base_dir in tp.parents or tp.parent == base_dir) and tp.exists() and tp.is_file():
                tp.unlink()
    except Exception as e:
        print(f"[RecordingsAPI] Thumbnail unlink warning: {e}")
