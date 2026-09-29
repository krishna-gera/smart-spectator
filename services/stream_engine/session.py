"""
Smart Spectator - Stream Session & Health Tracker
Manages state, decoded frame buffer, and telemetry metrics per active camera stream.
"""

import time
from typing import Optional, Dict, Any, List
import numpy as np
from .protocol import PacketHeader
from .decoder import H264Decoder


class StreamSession:
    """Represents an active video ingestion session for a specific camera_id."""

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.decoder = H264Decoder()
        self.start_time = time.time()
        self.last_frame_time = time.time()
        
        # Telemetry
        self.frames_received = 0
        self.bytes_received = 0
        self.last_sequence: Optional[int] = None
        self.dropped_packets = 0
        self.current_fps = 0.0
        self.current_bitrate_kbps = 0.0
        
        # Sliding window for FPS & Bitrate calculation
        self._fps_window_start = time.time()
        self._frames_in_window = 0
        self._bytes_in_window = 0
        
        # Latest decoded frame for live preview & snapshots
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_frame_pts: int = 0
        self.latest_frame_timestamp: float = 0.0

    def ingest_packet(self, header: PacketHeader, payload: bytes) -> List[np.ndarray]:
        """
        Processes validated packet from protocol decoder.
        Detects packet gaps, updates rolling metrics, and triggers decoding.
        """
        now = time.time()
        self.frames_received += 1
        self.bytes_received += len(payload)
        self.last_frame_time = now
        
        # Sequence number gap detection
        if self.last_sequence is not None:
            expected_seq = (self.last_sequence + 1) & 0xFFFFFFFF
            if header.sequence_number != expected_seq and header.sequence_number > expected_seq:
                gap = header.sequence_number - expected_seq
                self.dropped_packets += gap
        self.last_sequence = header.sequence_number

        # Update sliding window metrics (1-second intervals)
        self._frames_in_window += 1
        self._bytes_in_window += (len(payload) + 24)
        elapsed = now - self._fps_window_start
        if elapsed >= 1.0:
            self.current_fps = round(self._frames_in_window / elapsed, 1)
            self.current_bitrate_kbps = round((self._bytes_in_window * 8) / (elapsed * 1000), 1)
            self._fps_window_start = now
            self._frames_in_window = 0
            self._bytes_in_window = 0

        # Decode NAL unit
        decoded_frames = self.decoder.decode_packet(payload)
        if decoded_frames:
            self.latest_frame = decoded_frames[-1]
            self.latest_frame_pts = header.pts_us
            self.latest_frame_timestamp = now

        return decoded_frames

    def get_metrics(self) -> Dict[str, Any]:
        """Returns real-time session telemetry."""
        return {
            "camera_id": self.camera_id,
            "session_duration_seconds": round(time.time() - self.start_time, 1),
            "fps": self.current_fps,
            "bitrate_kbps": self.current_bitrate_kbps,
            "frames_received": self.frames_received,
            "dropped_packets": self.dropped_packets,
            "has_decoded_frame": self.latest_frame is not None
        }

    def close(self):
        self.decoder.reset()
        self.latest_frame = None
