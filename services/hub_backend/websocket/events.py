"""
Smart Spectator - Real-time Event Stream WebSocket (/api/v1/events/stream)
Conforms to Section 32 of Phase 4 specification.
Pushes event_created, event_updated, event_resolved, camera_connected, camera_disconnected, recording_created.
"""

import json
import asyncio
from typing import Set, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.event_engine import event_engine

router = APIRouter(tags=["Event Stream"])


class EventStreamHub:
    """Manages active WebSocket client connections for real-time event broadcasting."""

    def __init__(self):
        self.active_clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_clients.add(websocket)
        print(f"[EventStreamWS] Client connected. Total active clients: {len(self.active_clients)}")

    async def unregister(self, websocket: WebSocket):
        async with self._lock:
            self.active_clients.discard(websocket)
        print(f"[EventStreamWS] Client disconnected. Total active clients: {len(self.active_clients)}")

    async def broadcast(self, message_type: str, data: Dict[str, Any]):
        """Pushes typed event payload to all active client connections."""
        payload = json.dumps({"type": message_type, "data": data})
        async with self._lock:
            clients = list(self.active_clients)

        dead_clients = []
        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_clients.append(ws)

        if dead_clients:
            async with self._lock:
                for ws in dead_clients:
                    self.active_clients.discard(ws)


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
    Supports ping/pong heartbeats to keep local connection alive.
    """
    await event_stream_hub.register(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": msg.get("timestamp")}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        await event_stream_hub.unregister(websocket)
    except Exception as e:
        print(f"[EventStreamWS] Socket error: {e}")
        await event_stream_hub.unregister(websocket)
