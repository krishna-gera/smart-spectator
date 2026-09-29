"""
Smart Spectator - Hardware Inference Provider Abstraction & Manager
Strictly conforms to shared/protocols/inference_provider.py and docs/12_SNAPDRAGON_OPTIMIZATION.md
Detects real hardware capabilities (Hexagon NPU, CoreML/DirectML GPU, CPU).
"""

import time
import os
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

from shared.protocols.inference_provider import InferenceProvider
from shared.schemas.v1.models import HardwareBackend, ModelMetadata


class BaseORTInferenceProvider(InferenceProvider):
    """Base class for ONNX Runtime-backed execution providers."""

    def __init__(self, backend: HardwareBackend, execution_provider_name: str):
        self.backend = backend
        self.provider_name = execution_provider_name
        self.sessions: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict[str, Any]] = {}
        self.latency_history: Dict[str, List[float]] = {}

    def initialize(self, config: Dict[str, Any]) -> bool:
        return HAS_ORT

    def load_model(self, model_id: str, model_path: str, backend_preference: HardwareBackend) -> bool:
        if not HAS_ORT or not os.path.exists(model_path):
            return False

        try:
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 4
            
            # Configure available provider
            available = ort.get_available_providers()
            providers = [self.provider_name] if self.provider_name in available else ["CPUExecutionProvider"]
            
            session = ort.InferenceSession(model_path, sess_options, providers=providers)
            self.sessions[model_id] = session
            
            # Cache metadata
            inputs = session.get_inputs()
            outputs = session.get_outputs()
            self.model_metadata[model_id] = {
                "inputs": [i.name for i in inputs],
                "input_shapes": [i.shape for i in inputs],
                "outputs": [o.name for o in outputs],
                "active_provider": session.get_providers()[0]
            }
            self.latency_history[model_id] = []
            return True
        except Exception as e:
            print(f"[InferenceProvider] Error loading model '{model_id}' on {self.provider_name}: {e}")
            return False

    def unload_model(self, model_id: str) -> None:
        if model_id in self.sessions:
            del self.sessions[model_id]
            del self.model_metadata[model_id]
            del self.latency_history[model_id]

    def predict(self, model_id: str, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        session = self.sessions.get(model_id)
        if not session:
            raise RuntimeError(f"Model '{model_id}' is not loaded.")

        t0 = time.perf_counter()
        outputs = session.run(None, inputs)
        t_elapsed = (time.perf_counter() - t0) * 1000.0  # ms

        # Record rolling latency (last 100 iterations)
        history = self.latency_history.setdefault(model_id, [])
        history.append(t_elapsed)
        if len(history) > 100:
            history.pop(0)

        output_names = self.model_metadata[model_id]["outputs"]
        return {name: arr for name, arr in zip(output_names, outputs)}

    def batch_predict(self, model_id: str, inputs: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        return self.predict(model_id, inputs)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "backend": self.backend.value,
            "provider_name": self.provider_name,
            "is_available": HAS_ORT and (self.provider_name in ort.get_available_providers())
        }

    def get_performance(self, model_id: str) -> Dict[str, float]:
        history = self.latency_history.get(model_id, [])
        if not history:
            return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "fps": 0.0}
        
        arr = np.array(history)
        mean_ms = float(np.mean(arr))
        p50_ms = float(np.percentile(arr, 50))
        p95_ms = float(np.percentile(arr, 95))
        fps = round(1000.0 / mean_ms, 1) if mean_ms > 0 else 0.0

        return {
            "mean_ms": round(mean_ms, 2),
            "p50_ms": round(p50_ms, 2),
            "p95_ms": round(p95_ms, 2),
            "fps": fps
        }


class CPUInferenceProvider(BaseORTInferenceProvider):
    """Universal fallback CPU execution provider."""
    def __init__(self):
        super().__init__(HardwareBackend.CPU, "CPUExecutionProvider")


class CoreMLInferenceProvider(BaseORTInferenceProvider):
    """Apple Silicon CoreML GPU/ANE provider for macOS development host."""
    def __init__(self):
        super().__init__(HardwareBackend.GPU_COREML, "CoreMLExecutionProvider")


class DirectMLInferenceProvider(BaseORTInferenceProvider):
    """DirectML GPU provider for Windows systems."""
    def __init__(self):
        super().__init__(HardwareBackend.GPU_DIRECTML, "DmlExecutionProvider")


class QNNInferenceProvider(BaseORTInferenceProvider):
    """
    Qualcomm Neural Network (QNN) Execution Provider.
    Primary target for Snapdragon X-Series Hexagon NPU on Windows on ARM64.
    """
    def __init__(self):
        super().__init__(HardwareBackend.NPU_QNN, "QNNExecutionProvider")


class InferenceProviderManager:
    """
    Discovers, validates, and manages hardware execution providers.
    Enforces the dynamic fallback hierarchy: NPU (QNN) -> GPU (CoreML/DirectML) -> CPU.
    Never fabricates NPU execution.
    """

    def __init__(self):
        self.providers: Dict[HardwareBackend, InferenceProvider] = {
            HardwareBackend.CPU: CPUInferenceProvider(),
            HardwareBackend.GPU_COREML: CoreMLInferenceProvider(),
            HardwareBackend.GPU_DIRECTML: DirectMLInferenceProvider(),
            HardwareBackend.NPU_QNN: QNNInferenceProvider(),
        }

    def detect_available_backends(self) -> List[HardwareBackend]:
        """Queries actual runtime environment for supported providers."""
        if not HAS_ORT:
            return []
        
        available_ort = ort.get_available_providers()
        detected = []

        if "QNNExecutionProvider" in available_ort:
            detected.append(HardwareBackend.NPU_QNN)
        if "CoreMLExecutionProvider" in available_ort:
            detected.append(HardwareBackend.GPU_COREML)
        if "DmlExecutionProvider" in available_ort:
            detected.append(HardwareBackend.GPU_DIRECTML)
        if "CPUExecutionProvider" in available_ort:
            detected.append(HardwareBackend.CPU)

        return detected

    def get_preferred_provider(self, requested: Optional[str] = "auto") -> Tuple[HardwareBackend, InferenceProvider]:
        """
        Resolves provider according to user request or automated fallback hierarchy:
        NPU_QNN -> GPU (CoreML/DirectML) -> CPU.
        """
        detected = self.detect_available_backends()

        if requested and requested.lower() != "auto":
            req_lower = requested.lower()
            if req_lower == "npu":
                if HardwareBackend.NPU_QNN in detected:
                    return HardwareBackend.NPU_QNN, self.providers[HardwareBackend.NPU_QNN]
                else:
                    raise RuntimeError("QNN NPU provider requested but not supported on this platform/driver.")
            elif req_lower == "gpu":
                for b in [HardwareBackend.GPU_COREML, HardwareBackend.GPU_DIRECTML]:
                    if b in detected:
                        return b, self.providers[b]
                raise RuntimeError("GPU provider requested but no supported GPU provider found.")
            elif req_lower == "cpu":
                return HardwareBackend.CPU, self.providers[HardwareBackend.CPU]

        # Automatic Selection Hierarchy
        if HardwareBackend.NPU_QNN in detected:
            return HardwareBackend.NPU_QNN, self.providers[HardwareBackend.NPU_QNN]
        if HardwareBackend.GPU_COREML in detected:
            return HardwareBackend.GPU_COREML, self.providers[HardwareBackend.GPU_COREML]
        if HardwareBackend.GPU_DIRECTML in detected:
            return HardwareBackend.GPU_DIRECTML, self.providers[HardwareBackend.GPU_DIRECTML]

        return HardwareBackend.CPU, self.providers[HardwareBackend.CPU]


provider_manager = InferenceProviderManager()
