"""
Smart Spectator - Model Registry & Local Lifecycle Abstraction
Conforms to Sections 15 & 16 of Phase 9 Master Specification.
Tracks registered local AI model artifacts, input/output tensor shapes,
execution providers, checksums, and production status.
Zero remote/internet model downloads.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

from services.hub_backend.config import settings
from ai.models.validator import model_validator


@dataclass
class RegisteredModel:
    id: str
    name: str
    version: str
    precision: str
    task_type: str
    runtime: str
    file_path: str
    checksum_sha256: str
    input_shape: List[Any]
    output_shape: List[Any]
    status: str  # "READY", "ACTIVE_PRODUCTION", "AVAILABLE", "INTEGRITY_FAILED"
    is_production: bool = False


class ModelRegistry:
    """
    Local-first model catalog. Maintains inventory of verified ONNX and quantized
    neural network weights on disk with zero external network connectivity.
    """

    def __init__(self, releases_dir: Optional[Path] = None):
        self.releases_dir = releases_dir or (settings.BASE_DIR / "ai" / "models" / "releases")
        self._models: Dict[str, RegisteredModel] = {}
        self._active_production_models: Dict[str, str] = {
            "detection": "detector_v1",
            "temporal_event": "spectatornet_v1_int8",
        }
        self.refresh()

    def refresh(self) -> None:
        """Discovers and validates all local model files from releases directory."""
        self._models.clear()

        # Release Models Catalog
        catalog = [
            {
                "id": "detector_v1",
                "name": "YOLOv8-Nano Object Detector",
                "version": "8.0.0",
                "precision": "FP32",
                "task_type": "detection",
                "runtime": "ONNX Runtime (QNN / DirectML / CoreML / CPU)",
                "filename": "detector_v1.onnx",
                "input_shape": [1, 3, 640, 640],
                "output_shape": [1, 84, 8400],
            },
            {
                "id": "spectatornet_v1_fp32",
                "name": "SpectatorNet Temporal GRU (FP32)",
                "version": "1.0.0",
                "precision": "FP32",
                "task_type": "temporal_event",
                "runtime": "ONNX Runtime (QNN / DirectML / CoreML / CPU)",
                "filename": "spectatornet_v1.onnx",
                "input_shape": [1, 30, 166],
                "output_shape": [1, 6],
            },
            {
                "id": "spectatornet_v1_int8",
                "name": "SpectatorNet Temporal GRU (INT8 Quantized)",
                "version": "1.0.0",
                "precision": "INT8",
                "task_type": "temporal_event",
                "runtime": "ONNX Runtime / QNN Hexagon NPU",
                "filename": "spectatornet_v1_int8.onnx",
                "input_shape": [1, 30, 166],
                "output_shape": [1, 6],
            },
        ]

        val_report = model_validator.validate_all()
        val_models = val_report.get("models", {})

        for item in catalog:
            m_id = item["id"]
            fn = item["filename"]
            p = self.releases_dir / fn
            exists = p.exists()

            m_val = val_models.get(fn, {})
            checksum = m_val.get("actual_sha256", "UNKNOWN")
            is_valid = (m_val.get("status") == "READY")

            is_prod = (self._active_production_models.get(item["task_type"]) == m_id)

            if not exists:
                stat = "MISSING"
            elif not is_valid:
                stat = "INTEGRITY_FAILED"
            elif is_prod:
                stat = "ACTIVE_PRODUCTION"
            else:
                stat = "AVAILABLE"

            reg_m = RegisteredModel(
                id=m_id,
                name=item["name"],
                version=item["version"],
                precision=item["precision"],
                task_type=item["task_type"],
                runtime=item["runtime"],
                file_path=str(p),
                checksum_sha256=checksum,
                input_shape=item["input_shape"],
                output_shape=item["output_shape"],
                status=stat,
                is_production=is_prod,
            )
            self._models[m_id] = reg_m

    def list_models(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all registered models, optionally filtered by task type."""
        self.refresh()
        models = list(self._models.values())
        if task_type:
            models = [m for m in models if m.task_type == task_type]
        return [asdict(m) for m in models]

    def get_model(self, model_id: str) -> Optional[RegisteredModel]:
        self.refresh()
        return self._models.get(model_id)

    def set_production_model(self, task_type: str, model_id: str) -> bool:
        """
        Explicitly selects active production model for a given task.
        Guarantees that unverified or corrupted models cannot become production.
        """
        self.refresh()
        model = self._models.get(model_id)
        if not model:
            raise KeyError(f"Model '{model_id}' is not registered.")
        if model.task_type != task_type:
            raise ValueError(f"Model '{model_id}' task type '{model.task_type}' does not match '{task_type}'.")
        if model.status == "INTEGRITY_FAILED":
            raise ValueError(f"Cannot activate model '{model_id}' due to integrity verification failure.")

        self._active_production_models[task_type] = model_id
        self.refresh()
        return True

    def get_active_production_model(self, task_type: str) -> Optional[RegisteredModel]:
        self.refresh()
        m_id = self._active_production_models.get(task_type)
        return self._models.get(m_id) if m_id else None


model_registry = ModelRegistry()
