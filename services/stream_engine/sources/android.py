"""
Smart Spectator - Android Camera Source
Conforms to Section 17 of Phase 10 Specification.
Adapts current low-latency TCP H.264 Android camera node stream to the CameraSource interface.
"""

from typing import Dict, Any, Optional
import numpy as np

from services.stream_engine.sources.base import CameraSource
from services.stream_engine.server import stream_engine


class AndroidCameraSource(CameraSource):
    """
    Android phone camera source feeding H.264 bitstream over TCP (Port 8554).
    """

    def __init__(self, camera_id: str):
        super().__init__(camera_id=camera_id, source_type="android_tcp")

    def connect(self) -> bool:
        session = stream_engine.sessions.get(self.camera_id)
        if session:
            self.is_connected = True
            return True
        self.is_connected = False
        return False

    def read_frame(self) -> Optional[np.ndarray]:
        # Grabs most recent decoded frame from session if available
        session = stream_engine.sessions.get(self.camera_id)
        if not session:
            self.is_connected = False
            return None
        self.is_connected = True
        return session.latest_frame

    def disconnect(self) -> None:
        self.is_connected = False

    def get_stats(self) -> Dict[str, Any]:
        session = stream_engine.sessions.get(self.camera_id)
        if not session:
            return {
                "source_type": self.source_type,
                "camera_id": self.camera_id,
                "connected": False,
                "fps": 0.0,
                "dropped_frames": 0,
            }
        return {
            "source_type": self.source_type,
            "camera_id": self.camera_id,
            "connected": True,
            "fps": getattr(session, "current_fps", 0.0),
            "dropped_frames": getattr(session, "dropped_packets", 0),
        }
