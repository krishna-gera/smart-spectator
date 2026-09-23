"""
Vision provider factory — selects the right provider based on configuration.
Implements a fallback chain: Primary → Fallback → Mock.
"""
import structlog
from typing import Optional

from app.core.config import settings
from app.services.vision.base import VisionModelProvider, UNKNOWN_RESULT

log = structlog.get_logger(__name__)

_primary_provider: Optional[VisionModelProvider] = None
_fallback_provider: Optional[VisionModelProvider] = None


def get_vision_provider(force_provider: str | None = None) -> VisionModelProvider:
    """
    Return the configured vision provider.
    Falls back to mock if the configured provider is unavailable.
    """
    global _primary_provider

    provider_name = force_provider or settings.VISION_PROVIDER.lower()

    if _primary_provider is None or force_provider:
        _primary_provider = _create_provider(provider_name)

    return _primary_provider


def _create_provider(name: str) -> VisionModelProvider:
    """Instantiate a provider by name."""
    if name == "yolo":
        try:
            from app.services.vision.yolo_provider import YOLOProvider
            return YOLOProvider()
        except ImportError as e:
            log.warning("YOLO not available, falling back to mock", error=str(e))
            return _get_mock()

    elif name == "ollama":
        from app.services.vision.ollama_provider import OllamaProvider
        return OllamaProvider()

    elif name in ("mock", "demo"):
        return _get_mock()

    else:
        log.warning("Unknown vision provider, using mock", provider=name)
        return _get_mock()


def _get_mock() -> VisionModelProvider:
    from app.services.vision.mock_provider import MockProvider
    return MockProvider()


class FallbackVisionProvider(VisionModelProvider):
    """
    Wraps a chain of providers with automatic fallback.
    Primary (e.g., Ollama VLM) → Secondary (e.g., YOLO) → Mock
    """
    import numpy as np
    from typing import List

    def __init__(self, primary: VisionModelProvider, fallback: VisionModelProvider):
        self.primary = primary
        self.fallback = fallback

    async def analyze(self, image, task_context):
        try:
            result = await self.primary.analyze(image, task_context)
            if result.confidence >= settings.CONFIDENCE_THRESHOLD:
                return result
            log.info("Primary provider low confidence, trying fallback", confidence=result.confidence)
        except Exception as e:
            log.warning("Primary vision provider failed", error=str(e))

        try:
            return await self.fallback.analyze(image, task_context)
        except Exception as e:
            log.error("Fallback vision provider also failed", error=str(e))
            return UNKNOWN_RESULT

    async def detect_objects(self, image):
        try:
            return await self.primary.detect_objects(image)
        except Exception:
            return await self.fallback.detect_objects(image)

    async def classify_scene(self, image, labels):
        try:
            return await self.primary.classify_scene(image, labels)
        except Exception:
            return await self.fallback.classify_scene(image, labels)

    async def compare_frames(self, frame_a, frame_b):
        try:
            return await self.primary.compare_frames(frame_a, frame_b)
        except Exception:
            return await self.fallback.compare_frames(frame_a, frame_b)

    async def estimate_state(self, image, context):
        try:
            return await self.primary.estimate_state(image, context)
        except Exception:
            return await self.fallback.estimate_state(image, context)

    async def health_check(self):
        primary_health = await self.primary.health_check()
        fallback_health = await self.fallback.health_check()
        return {"primary": primary_health, "fallback": fallback_health}
