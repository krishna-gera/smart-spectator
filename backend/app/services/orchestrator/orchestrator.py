"""
AI Orchestrator — coordinates the full vision pipeline.

Flow:
  Frame → Preprocessor → Motion Detector → Object Detector
       → Vision Model → State Estimator → Rule Engine
       → Event Generator → Alert Engine → WebSocket
"""
import base64
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

import cv2
import numpy as np
import structlog

from app.services.rules.rule_engine import RuleEngine
from app.services.vision.base import AIResult, TaskContext
from app.services.vision.provider_factory import get_vision_provider

log = structlog.get_logger(__name__)

# Per-camera temporal observation buffers
_observation_buffers: Dict[str, Deque] = {}
_last_frames: Dict[str, np.ndarray] = {}

BUFFER_SIZE = 10  # Keep last N observations per camera


class FramePreprocessor:
    """Preprocess incoming frames before AI analysis."""

    TARGET_WIDTH = 640  # Model-friendly width
    JPEG_QUALITY = 80

    def preprocess(self, raw_bytes: bytes, content_type: str = "image/jpeg") -> Optional[np.ndarray]:
        """Decode and resize frame for analysis."""
        try:
            nparr = np.frombuffer(raw_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                return None

            h, w = image.shape[:2]
            if w > self.TARGET_WIDTH:
                scale = self.TARGET_WIDTH / w
                image = cv2.resize(image, (self.TARGET_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)

            return image
        except Exception as e:
            log.error("Frame preprocessing failed", error=str(e))
            return None

    def compute_diff_score(self, frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """Fast pixel-level difference score."""
        try:
            gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
            gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(gray_a, gray_b)
            return float(diff.mean()) / 255.0
        except Exception:
            return 1.0


class AIOrchestrator:
    """
    Coordinates the full AI pipeline for a single frame analysis.
    """

    def __init__(self):
        self.preprocessor = FramePreprocessor()
        self.rule_engine = RuleEngine()

    async def process_frame(
        self,
        frame_b64: str,
        camera_id: str,
        session_id: Optional[str],
        task_id: Optional[str],
        task_context: Optional[TaskContext] = None,
        task_config: Optional[dict] = None,
        monitoring_type: str = "CUSTOM",
    ) -> Optional[dict]:
        """
        Full analysis pipeline for a single frame.
        Returns structured result dict or None if processing failed.
        """
        pipeline_start = time.perf_counter()

        # ── Step 1: Decode and preprocess ──────────────────────────────────────
        raw_bytes = base64.b64decode(frame_b64)
        image = self.preprocessor.preprocess(raw_bytes)
        if image is None:
            log.error("Failed to preprocess frame", camera_id=camera_id)
            return None

        # ── Step 2: Motion detection (skip heavy model if nothing changed) ─────
        last_frame = _last_frames.get(camera_id)
        change_significant = True

        if last_frame is not None:
            diff_score = self.preprocessor.compute_diff_score(last_frame, image)
            change_significant = diff_score > 0.03
            if not change_significant:
                log.debug("Frame skipped — no significant change", camera_id=camera_id, diff=diff_score)
                # Still return last known state
                return self._get_last_observation(camera_id)

        _last_frames[camera_id] = image.copy()

        # ── Step 3: AI Analysis ────────────────────────────────────────────────
        provider = get_vision_provider()

        if task_context is None:
            task_context = TaskContext(
                task_title="Visual Monitoring",
                task_description="Monitor the scene for relevant changes.",
            )

        # Add observation history to context
        buffer = _observation_buffers.setdefault(camera_id, deque(maxlen=BUFFER_SIZE))
        task_context.history = list(buffer)

        ai_result: AIResult = await provider.analyze(image, task_context)

        # ── Step 4: Validate confidence ─────────────────────────────────────────
        ai_result.confidence = max(0.0, min(1.0, ai_result.confidence))

        # ── Step 5: Build observation dict ─────────────────────────────────────
        observation = {
            "camera_id": camera_id,
            "session_id": session_id,
            "state": ai_result.state,
            "confidence": ai_result.confidence,
            "objects": [{"label": o.label, "confidence": o.confidence} for o in ai_result.objects],
            "measurements": ai_result.measurements,
            "change_detected": change_significant,
            "severity": ai_result.severity,
            "explanation": ai_result.explanation,
            "provider": ai_result.provider,
            "inference_ms": ai_result.inference_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # ── Step 6: Temporal smoothing — update buffer ─────────────────────────
        buffer.append(observation)

        # ── Step 7: Rule evaluation ─────────────────────────────────────────────
        rule_result = None
        if task_config is not None:
            from app.models.models import MonitoringType
            try:
                mt = MonitoringType(monitoring_type)
            except ValueError:
                mt = MonitoringType.CUSTOM

            rule_result = self.rule_engine.evaluate(
                observation=observation,
                task_config=task_config,
                monitoring_type=mt,
                history=list(buffer)[:-1],  # History excluding current
            )
            observation["rule_triggered"] = rule_result.triggered
            observation["rule_event_type"] = rule_result.event_type.value if rule_result.event_type else None
            observation["rule_description"] = rule_result.description

        pipeline_ms = (time.perf_counter() - pipeline_start) * 1000
        observation["pipeline_ms"] = round(pipeline_ms, 2)

        log.info(
            "Frame analyzed",
            camera_id=camera_id,
            state=ai_result.state,
            confidence=f"{ai_result.confidence:.2f}",
            provider=ai_result.provider,
            pipeline_ms=f"{pipeline_ms:.0f}ms",
            rule_triggered=rule_result.triggered if rule_result else False,
        )

        return observation

    def _get_last_observation(self, camera_id: str) -> Optional[dict]:
        buffer = _observation_buffers.get(camera_id)
        if buffer:
            obs = dict(buffer[-1])
            obs["change_detected"] = False
            obs["cached"] = True
            return obs
        return None
