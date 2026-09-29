"""
Smart Spectator - WebSocket Control Channel (/api/v1/control/ws)
Implements docs/05_CAMERA_PROTOCOL.md and docs/04_NETWORK_ARCHITECTURE.md
"""

import json
import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from services.device_manager.manager import device_manager

router = APIRouter(tags=["Control Channel"])


class ControlChannelHub:
    """Maintains active WebSocket control sessions with camera nodes."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[device_id] = websocket
        device_manager.set_device_status(device_id, "connected")
        print(f"[ControlChannel] Node '{device_id}' connected to control channel.")

    def disconnect(self, device_id: str):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
            device_manager.set_device_status(device_id, "disconnected")
            print(f"[ControlChannel] Node '{device_id}' disconnected from control channel.")

    async def send_command(self, device_id: str, command: Dict[str, Any]) -> bool:
        """Sends a JSON control command to a connected camera node."""
        ws = self.active_connections.get(device_id)
        if ws:
            try:
                await ws.send_text(json.dumps(command))
                return True
            except Exception as e:
                print(f"[ControlChannel] Error sending command to '{device_id}': {e}")
        return False

    async def request_keyframe(self, device_id: str, camera_id: str):
        """Requests an immediate IDR keyframe from the camera encoder."""
        cmd = {
            "protocol": "ss_control_v1",
            "type": "device_control_command",
            "target_camera_id": camera_id,
            "action": "request_idr"
        }
        return await self.send_command(device_id, cmd)


control_hub = ControlChannelHub()


@router.websocket("/control/ws")
async def websocket_control_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Persistent bi-directional control socket.
    Node reports 1 Hz telemetry and receives dynamic encoding commands.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    device = device_manager.authenticate_token(token)
    if not device:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or revoked token")
        return

    device_id = device["device_id"]
    await control_hub.connect(device_id, websocket)

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                msg_type = data.get("type")

                if msg_type == "telemetry_report":
                    metrics = data.get("metrics", {})
                    device_manager.update_telemetry(
                        device_id=device_id,
                        battery_level=metrics.get("battery_level_percent"),
                        is_charging=metrics.get("is_charging"),
                        battery_temp_c=metrics.get("battery_temperature_c")
                    )
                elif msg_type == "command_ack":
                    # Node acknowledged command
                    pass
                elif msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": data.get("timestamp")}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        control_hub.disconnect(device_id)
    except Exception as e:
        print(f"[ControlChannel] Unexpected error with '{device_id}': {e}")
        control_hub.disconnect(device_id)
