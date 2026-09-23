"""
Ollama VLM provider — connects to local Ollama for open-source VLMs.
Supports: llava, qwen2.5-vl, moondream, bakllava, minicpm-v, etc.
"""
import base64
import json
import time
from typing import List

import httpx
import numpy as np
import structlog

from app.core.config import settings
from app.services.vision.base import (
    AIResult, BoundingBox, Detection, FrameDiff, SceneClassification,
    StateEstimate, TaskContext, VisionModelProvider, UNKNOWN_RESULT,
)

log = structlog.get_logger(__name__)

ANALYSIS_PROMPT_TEMPLATE = """You are Smart Spectator, an intelligent visual monitoring AI.

Monitoring Task: {task_title}
Description: {description}
Target Object: {target_object}
Condition to Monitor: {condition}

Analyze the provided image and respond ONLY with a valid JSON object matching this exact schema:
{{
  "state": "string (describe what you observe, e.g. WATER_LEVEL_RISING, DOOR_OPEN, MACHINE_RUNNING)",
  "confidence": number (0.0 to 1.0),
  "objects": [
    {{"label": "string", "confidence": number}}
  ],
  "measurements": {{"key": value}},
  "change_detected": boolean,
  "severity": "normal | warning | critical",
  "explanation": "string (1-2 sentences explaining what you see)"
}}

Be precise. Do not fabricate measurements you cannot observe. If uncertain, set confidence below 0.5.
Respond ONLY with the JSON object. No other text."""


class OllamaProvider(VisionModelProvider):
    """
    Ollama-based VLM provider for semantic scene understanding.
    Requires Ollama running locally with a vision model installed.
    Install: `ollama pull llava:7b`
    """

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_VLM_MODEL
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _encode_image(self, image: np.ndarray) -> str:
        """Encode numpy array to base64 JPEG."""
        import cv2
        _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buffer.tobytes()).decode("utf-8")

    async def _call_ollama(self, prompt: str, image_b64: str) -> str | None:
        """Make a call to the Ollama API."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 512,
            },
        }
        try:
            response = await self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except httpx.TimeoutException:
            log.error("Ollama request timed out", model=self.model)
            return None
        except Exception as e:
            log.error("Ollama request failed", error=str(e))
            return None

    def _parse_ai_response(self, raw: str) -> dict | None:
        """Extract and validate JSON from model response."""
        # Try to extract JSON even if model added surrounding text
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group())
            # Validate required fields
            if "state" not in data or "confidence" not in data:
                return None
            # Clamp confidence
            data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
            # Ensure required fields exist
            data.setdefault("objects", [])
            data.setdefault("measurements", {})
            data.setdefault("change_detected", False)
            data.setdefault("severity", "normal")
            data.setdefault("explanation", "")
            return data
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    async def analyze(self, image: np.ndarray, task_context: TaskContext) -> AIResult:
        start = time.perf_counter()
        image_b64 = await self._encode_image(image)

        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            task_title=task_context.task_title,
            description=task_context.task_description or "No description provided.",
            target_object=task_context.target_object or "any relevant objects",
            condition=task_context.condition or "Monitor for any significant changes.",
        )

        raw = await self._call_ollama(prompt, image_b64)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if raw is None:
            return UNKNOWN_RESULT

        parsed = self._parse_ai_response(raw)
        if parsed is None:
            log.warning("Could not parse VLM response", raw=raw[:200])
            return UNKNOWN_RESULT

        objects = [
            Detection(label=o.get("label", "unknown"), confidence=float(o.get("confidence", 0.0)))
            for o in parsed.get("objects", [])
        ]

        return AIResult(
            state=str(parsed["state"]).upper().replace(" ", "_")[:100],
            confidence=parsed["confidence"],
            objects=objects,
            measurements=parsed.get("measurements", {}),
            change_detected=bool(parsed.get("change_detected", False)),
            severity=parsed.get("severity", "normal"),
            explanation=str(parsed.get("explanation", ""))[:500],
            provider=f"ollama/{self.model}",
            inference_ms=elapsed_ms,
        )

    async def detect_objects(self, image: np.ndarray) -> List[Detection]:
        image_b64 = await self._encode_image(image)
        prompt = 'List all objects you can see in this image as JSON: {"objects": [{"label": "name", "confidence": 0.9}]}'
        raw = await self._call_ollama(prompt, image_b64)
        if not raw:
            return []
        parsed = self._parse_ai_response(raw)
        if not parsed:
            return []
        return [
            Detection(label=o.get("label", "unknown"), confidence=float(o.get("confidence", 0.5)))
            for o in parsed.get("objects", [])
        ]

    async def classify_scene(self, image: np.ndarray, labels: List[str]) -> SceneClassification:
        image_b64 = await self._encode_image(image)
        label_list = ", ".join(labels)
        prompt = f'Classify this image as one of: [{label_list}]. Respond with JSON: {{"label": "chosen_label", "confidence": 0.9}}'
        raw = await self._call_ollama(prompt, image_b64)
        if not raw:
            return SceneClassification(label="unknown", confidence=0.0)
        parsed = self._parse_ai_response(raw)
        if not parsed:
            return SceneClassification(label="unknown", confidence=0.0)
        return SceneClassification(label=parsed.get("state", "unknown"), confidence=parsed.get("confidence", 0.0))

    async def compare_frames(self, frame_a: np.ndarray, frame_b: np.ndarray) -> FrameDiff:
        """Use pixel-level comparison (VLMs are too slow for every frame)."""
        import cv2
        gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray_a, gray_b)
        diff_score = float(diff.mean()) / 255.0
        return FrameDiff(changed=diff_score > settings.FRAME_DIFF_THRESHOLD, diff_score=diff_score)

    async def estimate_state(self, image: np.ndarray, context: str) -> StateEstimate:
        image_b64 = await self._encode_image(image)
        prompt = f'Context: {context}\nDescribe the current state in JSON: {{"state": "STATE_NAME", "confidence": 0.9, "explanation": "brief explanation"}}'
        raw = await self._call_ollama(prompt, image_b64)
        if not raw:
            return StateEstimate(state="UNKNOWN", confidence=0.0)
        parsed = self._parse_ai_response(raw)
        if not parsed:
            return StateEstimate(state="UNKNOWN", confidence=0.0)
        return StateEstimate(
            state=str(parsed.get("state", "UNKNOWN")).upper().replace(" ", "_"),
            confidence=parsed.get("confidence", 0.0),
            explanation=str(parsed.get("explanation", "")),
        )

    async def health_check(self) -> dict:
        try:
            response = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            data = response.json()
            models = [m.get("name") for m in data.get("models", [])]
            return {
                "provider": "ollama",
                "base_url": self.base_url,
                "model": self.model,
                "available_models": models,
                "model_available": self.model in models,
                "status": "ok",
            }
        except Exception as e:
            return {"provider": "ollama", "status": "error", "detail": str(e)}
