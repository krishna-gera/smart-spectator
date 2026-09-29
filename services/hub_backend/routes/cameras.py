"""
Smart Spectator - Camera Management & Stream Control Routes
Implements docs/07_API_SPECIFICATION.md
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status, Response
from pydantic import BaseModel, Field

from ..database.connection import db_session

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", status_code=status.HTTP_200_OK)
def list_cameras():
    """Lists all registered cameras."""
    with db_session() as conn:
        cur = conn.execute("SELECT * FROM cameras ORDER BY created_at ASC")
        return cur.fetchall()


@router.get("/{camera_id}", status_code=status.HTTP_200_OK)
def get_camera(camera_id: str):
    """Retrieves camera configuration and active stream state."""
    with db_session() as conn:
        cur = conn.execute("SELECT * FROM cameras WHERE camera_id = ?", (camera_id,))
        cam = cur.fetchone()
        if not cam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
        return cam


@router.post("/{camera_id}/start", status_code=status.HTTP_200_OK)
def start_camera(camera_id: str):
    """Signals camera stream session activation."""
    with db_session() as conn:
        cur = conn.execute("UPDATE cameras SET status = 'streaming' WHERE camera_id = ?", (camera_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return {"camera_id": camera_id, "status": "streaming"}


@router.post("/{camera_id}/stop", status_code=status.HTTP_200_OK)
def stop_camera(camera_id: str):
    """Stops camera streaming session."""
    with db_session() as conn:
        cur = conn.execute("UPDATE cameras SET status = 'idle' WHERE camera_id = ?", (camera_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return {"camera_id": camera_id, "status": "idle"}
