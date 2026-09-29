"""
Smart Spectator - Real-time Event Stream WebSocket (/api/v1/events/stream)
Conforms to Section 32 of Phase 4 specification.
Pushes event_created, event_updated, event_resolved, camera_connected, camera_disconnected, recording_created.
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Set, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.event_engine import event_engine

router = APIRouter(tags=["Event Stream"])


class EventStreamHub:
    """Manages active WebSocket client connections for real-time event broadcasting with subscription filtering."""

    def __init__(self):
        self.active_clients: Set[WebSocket] = set()
        self.client_filters: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_clients.add(websocket)
            self.client_filters[websocket] = {}
        print(f"[EventStreamWS] Client connected. Total active clients: {len(self.active_clients)}")

    async def unregister(self, websocket: WebSocket):
        async with self._lock:
            self.active_clients.discard(websocket)
            self.client_filters.pop(websocket, None)
        print(f"[EventStreamWS] Client disconnected. Total active clients: {len(self.active_clients)}")

    def set_filter(self, websocket: WebSocket, filter_rules: Dict[str, Any]):
        """Sets subscription filter for a specific client."""
        self.client_filters[websocket] = filter_rules or {}

    def _matches_filter(self, ws: WebSocket, msg_type: str, data: Dict[str, Any]) -> bool:
        """Evaluates whether message passes client's subscription filter."""
        f = self.client_filters.get(ws, {})
        if not f:
            return True

        # Camera ID filter
        req_cam = f.get("camera_id")
        if req_cam and data.get("camera_id") and data.get("camera_id") != req_cam:
            return False

        # Event type filter
        req_types = f.get("event_types")
        if req_types and isinstance(req_types, list):
            evt_type = data.get("event_type") or msg_type
            if evt_type not in req_types and msg_type not in req_types:
                return False

        return True

    async def broadcast(self, message_type: str, data: Dict[str, Any]):
        """Pushes versioned event payload conforming to Section 26 to subscribed clients."""
        now_iso = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({
            "type": message_type,
            "schema_version": "1.2.0",
            "timestamp": now_iso,
            "data": data,
        })
        async with self._lock:
            clients = list(self.active_clients)

        dead_clients = []
        for ws in clients:
            if not self._matches_filter(ws, message_type, data):
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead_clients.append(ws)

        if dead_clients:
            async with self._lock:
                for ws in dead_clients:
                    self.active_clients.discard(ws)
                    self.client_filters.pop(ws, None)


event_stream_hub = EventStreamHub()


# Synchronous bridge from EventEngine thread to asyncio event loop
def _on_event_engine_broadcast(msg_type: str, data: Dict[str, Any]):
    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(event_stream_hub.broadcast(msg_type, data), loop)
    except RuntimeError:
        pass


# Register listener with EventEngine
event_engine.subscribe_websocket(_on_event_engine_broadcast)


@router.websocket("/events/stream")
async def events_websocket_endpoint(websocket: WebSocket):
    """
    Subscribes client to real-time event lifecycle stream.
    Supports ping/pong heartbeats and client subscription filtering.
    """
    await event_stream_hub.register(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                mtype = msg.get("type")
                if mtype == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "schema_version": "1.2.0",
                        "timestamp": msg.get("timestamp", datetime.now(timezone.utc).isoformat())
                    }))
                elif mtype == "subscribe":
                    filter_rules = msg.get("filter", {})
                    event_stream_hub.set_filter(websocket, filter_rules)
                    await websocket.send_text(json.dumps({
                        "type": "subscription_ack",
                        "schema_version": "1.2.0",
                        "filter": filter_rules,
                    }))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await event_stream_hub.unregister(websocket)
    except Exception as e:
        print(f"[EventStreamWS] Socket error: {e}")
        await event_stream_hub.unregister(websocket)
