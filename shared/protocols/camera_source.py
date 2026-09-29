"""
Smart Spectator - CameraSource Abstraction Interface
Decouples frame capture hardware/transports (Phone, RTSP, ONVIF, USB) from downstream AI and stream processing.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, AsyncIterator
import numpy as np


class CameraCapabilities:
    """Describes static and dynamic hardware/driver capabilities of a camera source."""
    def __init__(
        self,
        supported_resolutions: list[Tuple[int, int]],
        supported_fps: list[int],
        has_ptz: bool = False,
        has_audio: bool = False,
        hardware_h264_decode: bool = True
    ):
        self.supported_resolutions = supported_resolutions
        self.supported_fps = supported_fps
        self.has_ptz = has_ptz
        self.has_audio = has_audio
        self.hardware_h264_decode = hardware_h264_decode


class CameraSource(ABC):
    """
    Abstract interface required for any visual source integrated into Smart Spectator.
    Downstream frame pipelines and the AI Engine only interact through this contract.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """Establish network or hardware handshake with the camera."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully terminate stream and connection resources."""
        pass

    @abstractmethod
    async def start_stream(self) -> bool:
        """Begin stream reception and buffer allocation."""
        pass

    @abstractmethod
    async def stop_stream(self) -> None:
        """Halt streaming without tearing down the underlying control session."""
        pass

    @abstractmethod
    async def get_frame(self, timeout_ms: int = 1000) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Poll latest decoded frame buffer.
        Returns:
            Tuple containing:
            - ndarray: BGR or RGB frame data
            - Dict: Metadata (camera_id, frame_index, pts, timestamp)
        """
        pass

    @abstractmethod
    def frame_generator(self) -> AsyncIterator[Tuple[np.ndarray, Dict[str, Any]]]:
        """Asynchronous stream of raw decoded video frames."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Current operational status: connection health, frame rate, bitrate, drop rate."""
        pass

    @abstractmethod
    def get_capabilities(self) -> CameraCapabilities:
        """Query supported resolutions, frame rates, and control capabilities."""
        pass
