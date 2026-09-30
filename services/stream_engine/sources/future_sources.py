"""
Smart Spectator - Future Camera Source Interfaces
Conforms to Section 17 of Phase 10 Specification.
Defines clean structural stubs for future RTSP, ONVIF, and USB video feeds.
Strictly non-functional stubs awaiting future implementation phases.
"""

from typing import Dict, Any, Optional
import numpy as np

from services.stream_engine.sources.base import CameraSource


class RTSPCameraSource(CameraSource):
    """Future RTSP/H.264 network camera source stub."""

    def __init__(self, camera_id: str, rtsp_url: str):
        super().__init__(camera_id=camera_id, source_type="rtsp")
        self.rtsp_url = rtsp_url

    def connect(self) -> bool:
        raise NotImplementedError("RTSP camera ingestion is planned for a future release.")

    def read_frame(self) -> Optional[np.ndarray]:
        return None

    def disconnect(self) -> None:
        self.is_connected = False

    def get_stats(self) -> Dict[str, Any]:
        return {"source_type": self.source_type, "camera_id": self.camera_id, "connected": False}


class ONVIFCameraSource(CameraSource):
    """Future ONVIF PTZ/Fixed IP camera source stub."""

    def __init__(self, camera_id: str, host: str, port: int = 80):
        super().__init__(camera_id=camera_id, source_type="onvif")
        self.host = host
        self.port = port

    def connect(self) -> bool:
        raise NotImplementedError("ONVIF camera protocol is planned for a future release.")

    def read_frame(self) -> Optional[np.ndarray]:
        return None

    def disconnect(self) -> None:
        self.is_connected = False

    def get_stats(self) -> Dict[str, Any]:
        return {"source_type": self.source_type, "camera_id": self.camera_id, "connected": False}


class USBCameraSource(CameraSource):
    """Future DirectShow / V4L2 USB webcam source stub."""

    def __init__(self, camera_id: str, device_index: int = 0):
        super().__init__(camera_id=camera_id, source_type="usb")
        self.device_index = device_index

    def connect(self) -> bool:
        raise NotImplementedError("Direct USB camera capture is planned for a future release.")

    def read_frame(self) -> Optional[np.ndarray]:
        return None

    def disconnect(self) -> None:
        self.is_connected = False

    def get_stats(self) -> Dict[str, Any]:
        return {"source_type": self.source_type, "camera_id": self.camera_id, "connected": False}
