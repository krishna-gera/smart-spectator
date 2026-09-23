"""
YOLOv8 vision provider — fast object detection.
Uses Ultralytics YOLOv8 (open-source, Apache 2.0 license).
"""
import time
from typing import List

import numpy as np
import structlog

from app.core.config import settings
from app.services.vision.base import (
    AIResult, BoundingBox, Detection, FrameDiff, SceneClassification,
    StateEstimate, TaskContext, VisionModelProvider, UNKNOWN_RESULT,
)

log = structlog.get_logger(__name__)

_model = None


def _load_model():
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO
            model_size = settings.YOLO_MODEL_SIZE or "yolov8n"
            model_path = settings.YOLO_MODEL_PATH or model_size
            _model = YOLO(model_path)
            log.info("YOLO model loaded", model=model_path)
        except Exception as e:
            log.error("Failed to load YOLO model", error=str(e))
    return _model


class YOLOProvider(VisionModelProvider):
    """
    YOLOv8-based object detection provider.
    Excellent for object presence/absence, counting, and bounding-box localization.
    Runs efficiently on CPU with the nano (n) model.
    """

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            self._model = _load_model()
        return self._model

    async def detect_objects(self, image: np.ndarray) -> List[Detection]:
        model = self._get_model()
        if model is None:
            return []

        try:
            results = model.predict(image, verbose=False, conf=settings.CONFIDENCE_THRESHOLD)
            detections = []
            for r in results:
                for box in r.boxes:
                    label = r.names[int(box.cls[0])]
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    detections.append(Detection(
                        label=label,
                        confidence=conf,
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                        class_id=int(box.cls[0]),
                    ))
            return detections
        except Exception as e:
            log.error("YOLO detection failed", error=str(e))
            return []

    async def analyze(self, image: np.ndarray, task_context: TaskContext) -> AIResult:
        start = time.perf_counter()
        detections = await self.detect_objects(image)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if not detections:
            return AIResult(
                state="NO_OBJECTS_DETECTED",
                confidence=0.5,
                objects=[],
                explanation="No objects detected in frame.",
                provider="yolo",
                inference_ms=elapsed_ms,
            )

        # Find most relevant object based on task context
        target = task_context.target_object
        relevant = [d for d in detections if target and target.lower() in d.label.lower()] if target else detections
        top = sorted(relevant or detections, key=lambda d: d.confidence, reverse=True)

        state = "OBJECT_DETECTED"
        confidence = top[0].confidence if top else 0.0
        explanation = f"Detected {len(detections)} object(s). Top: {top[0].label} ({top[0].confidence:.0%})" if top else "Objects detected."

        return AIResult(
            state=state,
            confidence=confidence,
            objects=detections,
            change_detected=False,  # Determined by temporal analysis
            explanation=explanation,
            provider="yolo",
            inference_ms=elapsed_ms,
        )

    async def classify_scene(self, image: np.ndarray, labels: List[str]) -> SceneClassification:
        # YOLO doesn't do zero-shot classification, fall back to detection-based
        detections = await self.detect_objects(image)
        if not detections:
            return SceneClassification(label="unknown", confidence=0.0)
        top = max(detections, key=lambda d: d.confidence)
        return SceneClassification(label=top.label, confidence=top.confidence)

    async def compare_frames(self, frame_a: np.ndarray, frame_b: np.ndarray) -> FrameDiff:
        """Pixel-level frame difference using OpenCV."""
        import cv2
        try:
            gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
            gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray_a, gray_b)
            diff_score = float(diff.mean()) / 255.0
            changed = diff_score > settings.FRAME_DIFF_THRESHOLD
            return FrameDiff(changed=changed, diff_score=diff_score)
        except Exception as e:
            log.error("Frame comparison failed", error=str(e))
            return FrameDiff(changed=True, diff_score=1.0)

    async def estimate_state(self, image: np.ndarray, context: str) -> StateEstimate:
        """YOLO can't do NL state estimation — return detection-based state."""
        detections = await self.detect_objects(image)
        if not detections:
            return StateEstimate(state="UNKNOWN", confidence=0.0, explanation="No objects detected")
        top = max(detections, key=lambda d: d.confidence)
        return StateEstimate(
            state=f"{top.label.upper().replace(' ', '_')}_PRESENT",
            confidence=top.confidence,
            explanation=f"Detected {top.label} with {top.confidence:.0%} confidence.",
        )

    async def health_check(self) -> dict:
        model = self._get_model()
        return {
            "provider": "yolo",
            "model": settings.YOLO_MODEL_SIZE,
            "loaded": model is not None,
            "device": settings.DEVICE,
        }
