"""
Smart Spectator - Camera Source Abstraction
Conforms to Section 17 of Phase 10 Specification.
Defines clean polymorphic interfaces for current (Android) and future camera inputs
(RTSP, ONVIF, USB) without modifying downstream AI or recording layers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np


class CameraSource(ABC):
    """
    Polymorphic interface for visual ingest sources.
    Isolates frame acquisition protocols from downstream perception pipelines.
    """

    def __init__(self, camera_id: str, source_type: str):
        self.camera_id = camera_id
        self.source_type = source_type
        self.is_connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Establishes connection to the media source."""
        pass

    @abstractmethod
    def read_frame(self) -> Optional[np.ndarray]:
        """Returns the next decoded raw frame (BGR NumPy array), or None if unavailable."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Terminates source connection and cleans up underlying handles."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Returns ingestion telemetry (FPS, dropped frames, bitrate, resolution)."""
        pass
