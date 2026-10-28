"""
Smart Spectator - H.264 Video Stream Decoder
Decodes H.264 Annex-B NAL units into numpy BGR/RGB frame arrays.
Follows docs/02_ARCHITECTURE.md and docs/03_COMPONENT_ARCHITECTURE.md
"""

import logging
from typing import Optional, List, Tuple, Dict, Any
import numpy as np

logger = logging.getLogger("smart_spectator.stream_engine.decoder")

try:
    import av
    HAS_PYAV = True
except ImportError:
    HAS_PYAV = False


def is_keyframe_nal(nal_bytes: bytes) -> bool:
    """
    Checks if raw byte stream contains an H.264 SPS (7), PPS (8), or IDR (5) NAL unit.
    Handles standard 3-byte (0x000001) and 4-byte (0x00000001) start codes.
    """
    n = len(nal_bytes)
    i = 0
    while i < n - 4:
        if nal_bytes[i] == 0 and nal_bytes[i + 1] == 0:
            if nal_bytes[i + 2] == 1:
                nal_type = nal_bytes[i + 3] & 0x1F
                if nal_type in (5, 7, 8):
                    return True
                i += 3
            elif nal_bytes[i + 2] == 0 and nal_bytes[i + 3] == 1:
                if i + 4 < n:
                    nal_type = nal_bytes[i + 4] & 0x1F
                    if nal_type in (5, 7, 8):
                        return True
                i += 4
            else:
                i += 1
        else:
            i += 1
    return False


class H264Decoder:
    """
    Decodes incoming raw H.264 NAL units into raw image frames.
    Uses PyAV (FFmpeg libavcodec) as primary decoder.
    Enforces keyframe gating: discards inter-frames (P/B) until the first keyframe arrives.
    """

    def __init__(self):
        self.codec_context = None
        self.initialized = False
        self.has_received_keyframe = False
        
        # Telemetry metrics
        self.frames_decoded = 0
        self.decode_errors = 0
        self.keyframe_count = 0
        self.packets_dropped_before_keyframe = 0

        self._init_codec()

    def _init_codec(self):
        if HAS_PYAV:
            try:
                self.codec_context = av.CodecContext.create("h264", "r")
                self.initialized = True
            except Exception as e:
                logger.error(f"[Decoder] PyAV CodecContext init error: {e}")
                self.initialized = False
        else:
            logger.warning("[Decoder] PyAV not available. Operating in pass-through mode.")
            self.initialized = False

    def decode_packet(self, nal_payload: bytes, is_keyframe: bool = False) -> List[np.ndarray]:
        """
        Feeds raw H.264 NAL bytes into decoder.
        Returns list of decoded frames as BGR numpy arrays.
        Discards P-frames until an initial keyframe (SPS/PPS/IDR) is received.
        """
        frames: List[np.ndarray] = []
        if not self.initialized or not self.codec_context:
            return frames

        keyframe_detected = is_keyframe or is_keyframe_nal(nal_payload)

        # Gate P-frames until first keyframe arrives to prevent decode corruption
        if not self.has_received_keyframe:
            if not keyframe_detected:
                self.packets_dropped_before_keyframe += 1
                logger.debug("[Decoder] Dropping inter-frame packet prior to initial keyframe/IDR")
                return frames
            self.has_received_keyframe = True

        if keyframe_detected:
            self.keyframe_count += 1

        try:
            packet = av.Packet(nal_payload)
            decoded_frames = self.codec_context.decode(packet)
            for f in decoded_frames:
                img = f.to_ndarray(format="bgr24")
                frames.append(img)
            self.frames_decoded += len(frames)
        except Exception as e:
            self.decode_errors += 1
            logger.warning(f"[Decoder] Error decoding H.264 packet ({len(nal_payload)} bytes): {e}")

        return frames

    def get_metrics(self) -> Dict[str, Any]:
        """Returns decoder telemetry."""
        return {
            "frames_decoded": self.frames_decoded,
            "decode_errors": self.decode_errors,
            "keyframe_count": self.keyframe_count,
            "packets_dropped_before_keyframe": self.packets_dropped_before_keyframe,
            "has_received_keyframe": self.has_received_keyframe,
        }

    def reset(self):
        """Flushes decoder state upon stream reconnection or keyframe request."""
        self.has_received_keyframe = False
        self._init_codec()
