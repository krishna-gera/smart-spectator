"""
WebSocket hub — real-time camera status and AI results.
Channels are scoped by user_id and camera_id for privacy isolation.
"""
import json
from datetime import datetime, timezone
from typing import Dict, Set
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models.models import CameraDevice, User
from app.security.jwt import decode_token

log = structlog.get_logger(__name__)
router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections scoped per user and per camera.
    Ensures cross-user data isolation.
    """

    def __init__(self):
        # user_id -> set of websockets
        self._user_connections: Dict[str, Set[WebSocket]] = {}
        # camera_id -> set of websockets
        self._camera_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, camera_id: str | None = None):
        await websocket.accept()
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(websocket)

        if camera_id:
            if camera_id not in self._camera_connections:
                self._camera_connections[camera_id] = set()
            self._camera_connections[camera_id].add(websocket)

        log.info("WS connected", user_id=user_id, camera_id=camera_id)

    def disconnect(self, websocket: WebSocket, user_id: str, camera_id: str | None = None):
        if user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
        if camera_id and camera_id in self._camera_connections:
            self._camera_connections[camera_id].discard(websocket)
        log.info("WS disconnected", user_id=user_id, camera_id=camera_id)

    async def broadcast_to_camera(self, camera_id: str, message: dict):
        """Broadcast a message to all viewers watching a specific camera."""
        connections = self._camera_connections.get(camera_id, set()).copy()
        dead = set()
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._camera_connections[camera_id].discard(ws)

    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast a message to all connections for a user (e.g., alerts)."""
        connections = self._user_connections.get(user_id, set()).copy()
        dead = set()
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._user_connections[user_id].discard(ws)

    def get_active_count(self) -> dict:
        return {
            "users": len(self._user_connections),
            "cameras": len(self._camera_connections),
        }


# Global connection manager
manager = ConnectionManager()


async def _authenticate_ws(token: str | None) -> dict | None:
    """Validate a JWT token for WebSocket connections."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


@router.websocket("/ws/cameras/{camera_id}")
async def camera_websocket(
    websocket: WebSocket,
    camera_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time camera monitoring.
    Viewers subscribe here to receive live AI results and status updates.
    """
    payload = await _authenticate_ws(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload["sub"]

    # Verify the user has access to this camera
    async with AsyncSessionLocal() as db:
        cam_result = await db.execute(select(CameraDevice).where(CameraDevice.id == camera_id))
        camera = cam_result.scalar_one_or_none()
        if not camera:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Must be camera owner or authorized viewer
        if str(camera.user_id) != user_id:
            from app.models.models import DevicePair, PairingStatus, ViewerDevice
            pair_result = await db.execute(
                select(DevicePair)
                .join(ViewerDevice, DevicePair.viewer_device_id == ViewerDevice.id)
                .where(
                    DevicePair.camera_id == camera.id,
                    ViewerDevice.user_id == user_id,
                    DevicePair.status == PairingStatus.ACTIVE,
                )
            )
            if not pair_result.scalar_one_or_none():
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

    await manager.connect(websocket, user_id, camera_id)

    try:
        # Send initial state
        async with AsyncSessionLocal() as db:
            cam_result = await db.execute(select(CameraDevice).where(CameraDevice.id == camera_id))
            camera = cam_result.scalar_one_or_none()
            if camera:
                await websocket.send_json({
                    "type": "INITIAL_STATE",
                    "camera_id": camera_id,
                    "camera_name": camera.name,
                    "is_online": camera.is_online,
                    "is_monitoring": camera.is_monitoring,
                    "battery_level": camera.battery_level,
                    "network_type": camera.network_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            # Handle ping
            if msg.get("type") == "PING":
                await websocket.send_json({"type": "PONG", "timestamp": datetime.now(timezone.utc).isoformat()})

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, camera_id)
    except Exception as e:
        log.error("WebSocket error", error=str(e))
        manager.disconnect(websocket, user_id, camera_id)


@router.websocket("/ws/user")
async def user_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    User-level WebSocket for receiving alerts and notifications.
    """
    payload = await _authenticate_ws(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload["sub"]
    await manager.connect(websocket, user_id, camera_id=None)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "PING":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, camera_id=None)


# ─── WebRTC P2P Signaling Hub ─────────────────────────────────────────────────
# Relays SDP offers, answers, and ICE candidates between CAM CODER and VIEW ACCESS
# without touching video media or holding state authority.

_signaling_rooms: Dict[str, Set[WebSocket]] = {}

@router.websocket("/ws/signaling")
async def webrtc_signaling_websocket(
    websocket: WebSocket,
    camera_id: str = Query(...),
    client_id: str = Query(...),
):
    """
    Lightweight WebRTC signaling hub.
    Exchanges SDP offer, answer, and ICE candidate packets between peers.
    """
    await websocket.accept()
    if camera_id not in _signaling_rooms:
        _signaling_rooms[camera_id] = set()
    _signaling_rooms[camera_id].add(websocket)
    log.info("Signaling peer connected", camera_id=camera_id, client_id=client_id)

    try:
        while True:
            data = await websocket.receive_text()
            packet = json.loads(data)
            # Broadcast to other peers in the room
            peers = _signaling_rooms.get(camera_id, set()).copy()
            for peer in peers:
                if peer != websocket:
                    try:
                        await peer.send_text(data)
                    except Exception:
                        _signaling_rooms[camera_id].discard(peer)
    except WebSocketDisconnect:
        if camera_id in _signaling_rooms:
            _signaling_rooms[camera_id].discard(websocket)
        log.info("Signaling peer disconnected", camera_id=camera_id, client_id=client_id)

