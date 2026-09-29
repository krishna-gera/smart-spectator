"""
Smart Spectator - AI Debug Overlay Visualizer
Implements Section 30: Development visualizer rendering bounding boxes,
class names, persistent track IDs, and live inference metrics.
"""

from typing import Optional
import numpy as np
import cv2

from shared.schemas.v1.models import Observation


def draw_debug_overlay(
    frame: np.ndarray,
    observation: Optional[Observation] = None,
    fps: float = 0.0,
    provider_name: str = "CPU"
) -> np.ndarray:
    """
    Renders spatial detection bounding boxes, persistent track IDs,
    and telemetry diagnostics onto an image frame.
    """
    canvas = frame.copy()
    h, w = canvas.shape[:2]

    if observation:
        # 1. Draw Active Tracked Objects & Bounding Boxes
        for track in observation.tracked_objects:
            if not track.is_active:
                continue

            # Convert normalized coordinates [0, 1] to pixel coordinates
            x1 = int(track.current_bbox[0] * w)
            y1 = int(track.current_bbox[1] * h)
            x2 = int(track.current_bbox[2] * w)
            y2 = int(track.current_bbox[3] * h)

            # Assign color based on track_id
            color_id = (track.track_id * 67) % 255
            color = (
                int((color_id * 3) % 255),
                int((color_id * 7) % 255),
                int((color_id * 11) % 255)
            )

            # Draw bounding box
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

            # Draw label banner
            label = f"#{track.track_id} {track.class_name.upper()} {int(track.confidence * 100)}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            
            label_y = max(y1, text_h + 4)
            cv2.rectangle(canvas, (x1, label_y - text_h - 4), (x1 + text_w + 6, label_y + baseline - 2), color, -1)
            cv2.putText(canvas, label, (x1 + 3, label_y - 2), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

            # Draw trajectory path
            if len(track.trajectory) > 1:
                pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in track.trajectory], dtype=np.int32)
                cv2.polylines(canvas, [pts], False, color, 1, cv2.LINE_AA)

    # 2. Draw Top Telemetry Bar
    diag_text = f"AI FPS: {fps:.1f} | Backend: {provider_name}"
    cv2.rectangle(canvas, (10, 10), (320, 38), (15, 23, 42), -1)
    cv2.rectangle(canvas, (10, 10), (320, 38), (56, 189, 248), 1)
    cv2.putText(canvas, diag_text, (18, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (56, 189, 248), 1, cv2.LINE_AA)

    return canvas
