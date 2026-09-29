"""
Smart Spectator - Media Streaming & Live Preview Routes
Implements docs/07_API_SPECIFICATION.md and Phase 1 Step 18 (Basic Live Preview)
"""

import asyncio
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from services.device_manager.manager import device_manager
from services.stream_engine.server import stream_engine
from ..database.connection import db_session

router = APIRouter(prefix="/streams", tags=["Streaming & Ingestion"])


@router.websocket("/ingest/{camera_id}")
async def websocket_media_ingest(
    websocket: WebSocket,
    camera_id: str,
    token: Optional[str] = Query(None)
):
    """
    Authenticated media ingestion WebSocket endpoint.
    Camera nodes transmit continuous binary frames adhering to SS-DOC-005.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return

    device = device_manager.authenticate_token(token)
    if not device:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or revoked token")
        return

    await websocket.accept()
    session = stream_engine.get_or_create_session(camera_id)
    print(f"[MediaIngest] Ingest session opened for camera '{camera_id}' from device '{device['device_name']}'")

    try:
        while True:
            # Receive raw binary packet (24-byte header + H.264 NAL)
            raw_bytes = await websocket.receive_bytes()
            stream_engine.process_binary_chunk(camera_id, raw_bytes)
    except WebSocketDisconnect:
        print(f"[MediaIngest] Ingest session disconnected for camera '{camera_id}'")
        stream_engine.remove_session(camera_id)
    except Exception as e:
        print(f"[MediaIngest] Error during media ingest for '{camera_id}': {e}")
        stream_engine.remove_session(camera_id)


@router.get("", status_code=status.HTTP_200_OK)
def list_active_streams():
    """Returns telemetry metrics for all actively streaming cameras."""
    metrics = []
    for cam_id, session in stream_engine.sessions.items():
        metrics.append(session.get_metrics())
    return metrics


@router.get("/{camera_id}/snapshot", status_code=status.HTTP_200_OK)
def get_camera_snapshot(camera_id: str):
    """Returns latest decoded frame as an image/jpeg payload."""
    jpeg_bytes = stream_engine.get_latest_jpeg(camera_id)
    if not jpeg_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No decoded frame available yet for this camera"
        )
    return Response(content=jpeg_bytes, media_type="image/jpeg")


@router.get("/{camera_id}/preview")
async def get_live_mjpeg_preview(camera_id: str):
    """
    Continuous Multipart MJPEG stream for basic live preview directly in browser.
    Renders live video without requiring third-party video players.
    """
    async def frame_stream_generator():
        while True:
            jpeg_bytes = stream_engine.get_latest_jpeg(camera_id)
            if jpeg_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
                )
            await asyncio.sleep(0.033)  # ~30 FPS

    return StreamingResponse(
        frame_stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )
