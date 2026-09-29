"""
Smart Spectator - InferenceProvider Abstraction Interface
Decouples model execution from underlying hardware runtimes (Qualcomm QNN / DirectML / CoreML / CPU).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import numpy as np
from ..schemas.v1.models import HardwareBackend, ModelMetadata


class InferenceProvider(ABC):
    """
    Abstract Hardware-agnostic backend execution engine.
    Wraps runtime execution (ONNX Runtime, Qualcomm QNN SDK, DirectML, CoreML).
    """

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize runtime context, assign hardware accelerators."""
        pass

    @abstractmethod
    def load_model(self, model_id: str, model_path: str, backend_preference: HardwareBackend) -> bool:
        """Load and compile/bind model artifact to target compute unit."""
        pass

    @abstractmethod
    def unload_model(self, model_id: str) -> None:
        """Free memory and runtime sessions associated with model."""
        pass

    @abstractmethod
    def predict(self, model_id: str, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Synchronous or asynchronous forward pass over input tensors."""
        pass

    @abstractmethod
    def batch_predict(self, model_id: str, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Optimized forward pass over batched tensors across multiple cameras."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Query available execution units: Hexagon NPU, Adreno GPU, Kryo CPU."""
        pass

    @abstractmethod
    def get_performance(self, model_id: str) -> Dict[str, float]:
        """Return rolling latency (p50, p95, p99 ms), memory consumption, and FPS."""
        pass
