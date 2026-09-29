"""
Smart Spectator - H.264 Video Stream Decoder
Decodes H.264 Annex-B NAL units into numpy BGR/RGB frame arrays.
Follows docs/02_ARCHITECTURE.md and docs/03_COMPONENT_ARCHITECTURE.md
"""

from typing import Optional, List, Tuple
import numpy as np

try:
    import av
    HAS_PYAV = True
except ImportError:
    HAS_PYAV = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class H264Decoder:
    """
    Decodes incoming raw H.264 NAL units into raw image frames.
    Uses PyAV (FFmpeg libavcodec) as primary decoder with fallback.
    """

    def __init__(self):
        self.codec_context = None
        self.initialized = False
        self._init_codec()

    def _init_codec(self):
        if HAS_PYAV:
            try:
                self.codec_context = av.CodecContext.create("h264", "r")
                self.initialized = True
            except Exception as e:
                print(f"[Decoder] PyAV CodecContext init error: {e}")
                self.initialized = False
        else:
            print("[Decoder] PyAV not available yet. Operating in pass-through mode.")

    def decode_packet(self, nal_payload: bytes) -> List[np.ndarray]:
        """
        Feeds raw H.264 NAL bytes into decoder.
        Returns list of decoded frames as BGR/RGB numpy arrays.
        """
        frames: List[np.ndarray] = []
        if not self.initialized or not self.codec_context:
            return frames

        try:
            packet = av.Packet(nal_payload)
            decoded_frames = self.codec_context.decode(packet)
            for f in decoded_frames:
                # Convert to BGR format for standard OpenCV/NumPy consumption
                img = f.to_ndarray(format="bgr24")
                frames.append(img)
        except Exception as e:
            # Handle occasional packet decoding noise before keyframe arrival
            pass

        return frames

    def reset(self):
        """Flushes decoder state upon stream reconnection or keyframe request."""
        self._init_codec()
