"""
Smart Spectator - Privacy-Preserving Video Handling
Conforms to Sections 26 & 27 of Phase 10 Specification.
Applies geometric privacy masks and zone redactions to video frames
prior to disk persistence or client streaming.
Strictly prohibits facial recognition and biometric identification.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np


class PrivacyMaskEngine:
    """
    Applies privacy masks (opaque rectangles or zeroing) to sensitive regions
    of video frames without biometric or facial identification.
    """

    def __init__(self):
        self._masks: Dict[str, List[Tuple[float, float, float, float]]] = {}  # camera_id -> list of normalized [x1, y1, x2, y2]

    def set_privacy_masks(self, camera_id: str, normalized_boxes: List[Tuple[float, float, float, float]]) -> None:
        """Sets normalized rectangular privacy mask regions [x1, y1, x2, y2] for a camera."""
        self._masks[camera_id] = normalized_boxes

    def get_privacy_masks(self, camera_id: str) -> List[Tuple[float, float, float, float]]:
        return self._masks.get(camera_id, [])

    def apply_mask(self, camera_id: str, frame: np.ndarray, fill_color: Tuple[int, int, int] = (0, 0, 0)) -> np.ndarray:
        """
        Applies configured privacy masks directly to the frame in-place.
        """
        boxes = self._masks.get(camera_id)
        if not boxes or frame is None:
            return frame

        h, w = frame.shape[:2]
        masked = frame.copy()

        for box in boxes:
            x1 = max(0, min(w - 1, int(box[0] * w)))
            y1 = max(0, min(h - 1, int(box[1] * h)))
            x2 = max(0, min(w, int(box[2] * w)))
            y2 = max(0, min(h, int(box[3] * h)))

            if x2 > x1 and y2 > y1:
                masked[y1:y2, x1:x2] = fill_color

        return masked


privacy_mask_engine = PrivacyMaskEngine()
