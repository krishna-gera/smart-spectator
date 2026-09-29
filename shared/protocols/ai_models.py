"""
Smart Spectator - AI Model Abstractions
Defines standardized interfaces for Level 1 (Detector), Level 2 (Tracker), and Level 3 (Temporal/Event) models.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import numpy as np
from ..schemas.v1.models import Detection, TrackedObject, Observation, ModelMetadata


class AIModel(ABC):
    """Base interface for all AI perception and reasoning components."""

    @abstractmethod
    def load(self, weights_path: str, provider: Any) -> bool:
        """Bind model weights and assign execution provider."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release compute graph and buffers."""
        pass

    @abstractmethod
    def get_metadata(self) -> ModelMetadata:
        """Retrieve static model profile, input dimensions, and runtime target."""
        pass

    @abstractmethod
    def get_performance(self) -> Dict[str, float]:
        """Query real-time inference latency and throughput."""
        pass


class ObjectDetector(AIModel):
    """Level 1 Perception: Single-frame spatial detection."""

    @abstractmethod
    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.45) -> List[Detection]:
        """
        Execute spatial detection on a single RGB/BGR frame.
        Returns list of standardized Detection objects with normalized bounding boxes.
        """
        pass

    @abstractmethod
    def batch_detect(self, frames: List[np.ndarray], confidence_threshold: float = 0.45) -> List[List[Detection]]:
        """Multi-camera parallel detection."""
        pass


class ObjectTracker(ABC):
    """Level 2 Perception: Multi-object temporal association and tracklet state management."""

    @abstractmethod
    def update(self, camera_id: str, detections: List[Detection], timestamp: float) -> List[TrackedObject]:
        """
        Associate detections to historical tracks across frames.
        Maintains unique track IDs, velocity vectors, and trajectory history.
        """
        pass

    @abstractmethod
    def reset(self, camera_id: Optional[str] = None) -> None:
        """Clear active tracks for a camera stream or globally."""
        pass


class EventModel(AIModel):
    """
    Level 3 Perception: Custom SpectatorNet temporal event classifier.
    Analyzes temporal window of spatial embeddings / bounding box sequences.
    """

    @abstractmethod
    def predict_event(
        self,
        temporal_features: np.ndarray,
        track_history: List[TrackedObject],
        scene_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Infers temporal action or state transition:
        e.g., OBJECT_REMOVED, PERSON_ENTERED, CAMERA_BLOCKED, ABNORMAL_ACTIVITY.
        Returns:
            Dictionary containing event_type, confidence, and temporal metadata.
        """
        pass


class VisionLanguageModel(AIModel):
    """Future Level 4 Assistant: Zero-shot prompt queries and open-vocabulary understanding."""

    @abstractmethod
    def query_scene(self, frame: np.ndarray, prompt: str) -> str:
        """Answer natural language queries regarding current visual state."""
        pass
