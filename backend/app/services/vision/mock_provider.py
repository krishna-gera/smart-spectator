"""
Mock provider for demo/testing mode.
Simulates realistic AI responses without needing a real vision model.
"""
import asyncio
import math
import random
import time
from typing import List

import numpy as np

from app.services.vision.base import (
    AIResult, Detection, FrameDiff, SceneClassification,
    StateEstimate, TaskContext, VisionModelProvider,
)


class MockProvider(VisionModelProvider):
    """
    Demo-mode vision provider.
    Simulates a washing machine water level scenario by default.
    Safe to use in development without any model dependencies.
    """

    def __init__(self, scenario: str = "water_level"):
        self.scenario = scenario
        self._frame_count = 0
        self._simulated_level = 20.0  # Start at 20%

    async def detect_objects(self, image: np.ndarray) -> List[Detection]:
        await asyncio.sleep(0.05)  # Simulate inference delay
        return [
            Detection(label="washing_machine", confidence=0.97),
            Detection(label="water", confidence=0.85),
        ]

    async def analyze(self, image: np.ndarray, task_context: TaskContext) -> AIResult:
        start = time.perf_counter()
        await asyncio.sleep(0.1)  # Simulate processing

        self._frame_count += 1

        # Simulate water level rising over time
        self._simulated_level = min(100.0, self._simulated_level + random.uniform(2.0, 5.0))
        level = self._simulated_level

        if level >= 80:
            state = "WATER_LEVEL_THRESHOLD_REACHED"
            severity = "warning"
            explanation = f"Water level has reached approximately {level:.0f}%. Monitoring task condition met."
            confidence = 0.95
        elif level >= 60:
            state = "WATER_LEVEL_HIGH"
            severity = "normal"
            explanation = f"Water level is at approximately {level:.0f}% and rising."
            confidence = 0.91
        elif level >= 40:
            state = "WATER_LEVEL_RISING"
            severity = "normal"
            explanation = f"Water level is at approximately {level:.0f}%, continuing to rise."
            confidence = 0.88
        else:
            state = "WATER_LEVEL_LOW"
            severity = "normal"
            explanation = f"Water level is at approximately {level:.0f}%. Monitoring in progress."
            confidence = 0.84

        elapsed_ms = (time.perf_counter() - start) * 1000

        return AIResult(
            state=state,
            confidence=confidence,
            objects=[
                Detection(label="washing_machine", confidence=0.97),
                Detection(label="water", confidence=confidence - 0.05),
            ],
            measurements={"water_level_percent": round(level, 1)},
            change_detected=self._frame_count > 1,
            severity=severity,
            explanation=explanation,
            provider="mock",
            inference_ms=elapsed_ms,
        )

    async def classify_scene(self, image: np.ndarray, labels: List[str]) -> SceneClassification:
        await asyncio.sleep(0.05)
        return SceneClassification(label=labels[0] if labels else "unknown", confidence=0.9)

    async def compare_frames(self, frame_a: np.ndarray, frame_b: np.ndarray) -> FrameDiff:
        await asyncio.sleep(0.01)
        diff_score = random.uniform(0.02, 0.08)
        return FrameDiff(changed=diff_score > 0.05, diff_score=diff_score)

    async def estimate_state(self, image: np.ndarray, context: str) -> StateEstimate:
        await asyncio.sleep(0.05)
        level = self._simulated_level
        return StateEstimate(
            state=f"WATER_LEVEL_{int(level)}PCT",
            confidence=0.90,
            measurements={"water_level_percent": round(level, 1)},
            explanation=f"Simulated water level at {level:.0f}%.",
        )

    async def health_check(self) -> dict:
        return {
            "provider": "mock",
            "status": "ok",
            "scenario": self.scenario,
            "frame_count": self._frame_count,
            "simulated_level": round(self._simulated_level, 1),
        }

    def reset(self, level: float = 20.0):
        """Reset simulation state."""
        self._frame_count = 0
        self._simulated_level = level
