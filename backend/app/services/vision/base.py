"""
Abstract VisionModelProvider interface.
All vision model implementations must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np


@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def area(self) -> float:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: Optional[BoundingBox] = None
    class_id: Optional[int] = None


@dataclass
class SceneClassification:
    label: str
    confidence: float
    all_labels: List[dict] = field(default_factory=list)


@dataclass
class FrameDiff:
    changed: bool
    diff_score: float  # 0.0 = identical, 1.0 = completely different
    changed_regions: List[BoundingBox] = field(default_factory=list)


@dataclass
class StateEstimate:
    state: str
    confidence: float
    measurements: dict = field(default_factory=dict)
    explanation: str = ""


@dataclass
class TaskContext:
    """Context provided to vision models to guide analysis."""
    task_title: str
    task_description: str
    target_object: Optional[str] = None
    threshold: Optional[float] = None
    monitoring_type: str = "CUSTOM"
    condition: Optional[str] = None
    history: List[dict] = field(default_factory=list)


@dataclass
class AIResult:
    """Structured AI analysis result — always validated before use."""
    state: str
    confidence: float
    objects: List[Detection] = field(default_factory=list)
    measurements: dict = field(default_factory=dict)
    change_detected: bool = False
    severity: str = "normal"
    explanation: str = ""
    provider: str = "unknown"
    inference_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "confidence": round(max(0.0, min(1.0, self.confidence)), 4),
            "objects": [
                {
                    "label": o.label,
                    "confidence": round(o.confidence, 4),
                    "bbox": {
                        "x1": o.bbox.x1, "y1": o.bbox.y1,
                        "x2": o.bbox.x2, "y2": o.bbox.y2,
                    } if o.bbox else None,
                }
                for o in self.objects
            ],
            "measurements": self.measurements,
            "change_detected": self.change_detected,
            "severity": self.severity,
            "explanation": self.explanation,
            "provider": self.provider,
            "inference_ms": round(self.inference_ms, 2),
        }


UNKNOWN_RESULT = AIResult(
    state="UNKNOWN",
    confidence=0.0,
    explanation="Unable to confidently determine state.",
    provider="fallback",
)


class VisionModelProvider(ABC):
    """
    Abstract base for all vision model providers.
    Implement this to add a new model (YOLO, Florence, Qwen-VL, etc.).
    """

    @abstractmethod
    async def analyze(self, image: np.ndarray, task_context: TaskContext) -> AIResult:
        """Full analysis for a monitoring task."""
        pass

    @abstractmethod
    async def detect_objects(self, image: np.ndarray) -> List[Detection]:
        """Fast object detection pass."""
        pass

    @abstractmethod
    async def classify_scene(self, image: np.ndarray, labels: List[str]) -> SceneClassification:
        """Zero-shot scene classification."""
        pass

    @abstractmethod
    async def compare_frames(self, frame_a: np.ndarray, frame_b: np.ndarray) -> FrameDiff:
        """Detect changes between two consecutive frames."""
        pass

    @abstractmethod
    async def estimate_state(self, image: np.ndarray, context: str) -> StateEstimate:
        """Natural-language state estimation."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Return provider health information."""
        pass

    def get_name(self) -> str:
        return self.__class__.__name__
