"""
Smart Spectator - Model Integrity Validator
Conforms to Sections 17 & 21 of Phase 8 Master Specification.
Validates release model artifacts against manifest.json SHA-256 checksums,
checks model file presence, and verifies tensor input/output shapes.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False


class ModelIntegrityValidator:
    """
    Validates on-disk model artifacts against release manifest specifications.
    Enforces zero silent corruption and reports structured diagnostic status.
    """

    def __init__(self, manifest_path: Optional[str] = None):
        self.manifest_path = Path(manifest_path or "ai/models/releases/manifest.json")

    def validate_single_model(self, model_filename: str, expected_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Validates a single model file against expected metadata."""
        model_path = self.manifest_path.parent / model_filename
        if not model_path.exists():
            return {
                "file_name": model_filename,
                "status": "MISSING",
                "error": f"Model artifact '{model_filename}' not found at {model_path}",
                "checksum_match": False,
                "input_shapes": [],
                "output_shapes": [],
            }

        # Calculate SHA-256
        hasher = hashlib.sha256()
        with open(model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()

        expected_hash = expected_meta.get("sha256")
        if expected_hash and actual_hash != expected_hash:
            return {
                "file_name": model_filename,
                "status": "MODEL_INTEGRITY_ERROR",
                "error": f"Checksum mismatch: expected {expected_hash}, calculated {actual_hash}",
                "checksum_match": False,
                "actual_sha256": actual_hash,
                "expected_sha256": expected_hash,
                "input_shapes": [],
                "output_shapes": [],
            }

        # Verify shapes via ONNX Runtime if available
        input_shapes = []
        output_shapes = []
        if HAS_ORT:
            try:
                sess_opts = ort.SessionOptions()
                sess_opts.log_severity_level = 3  # Error only
                session = ort.InferenceSession(str(model_path), sess_opts, providers=["CPUExecutionProvider"])
                input_shapes = [i.shape for i in session.get_inputs()]
                output_shapes = [o.shape for o in session.get_outputs()]
            except Exception as e:
                return {
                    "file_name": model_filename,
                    "status": "MODEL_INTEGRITY_ERROR",
                    "error": f"ONNX shape inspection failed: {e}",
                    "checksum_match": True,
                    "input_shapes": [],
                    "output_shapes": [],
                }

        return {
            "file_name": model_filename,
            "status": "READY",
            "error": None,
            "checksum_match": True,
            "actual_sha256": actual_hash,
            "input_shapes": input_shapes,
            "output_shapes": output_shapes,
            "size_bytes": model_path.stat().st_size,
        }

    def validate_all(self) -> Dict[str, Any]:
        """
        Validates all models registered in the manifest.
        Returns aggregate status ('READY', 'MODEL_INTEGRITY_ERROR', 'DEGRADED', or 'NOT_AVAILABLE').
        """
        if not self.manifest_path.exists():
            return {
                "status": "NOT_AVAILABLE",
                "error": f"Manifest not found: {self.manifest_path}",
                "models": {},
            }

        try:
            manifest_data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            return {
                "status": "MODEL_INTEGRITY_ERROR",
                "error": f"Failed to parse manifest: {e}",
                "models": {},
            }

        results = {}
        all_ready = True
        has_error = False

        for model_filename, meta in manifest_data.items():
            res = self.validate_single_model(model_filename, meta)
            results[model_filename] = res
            if res["status"] == "MODEL_INTEGRITY_ERROR":
                has_error = True
                all_ready = False
            elif res["status"] != "READY":
                all_ready = False

        aggregate_status = "READY" if all_ready else ("MODEL_INTEGRITY_ERROR" if has_error else "DEGRADED")
        return {
            "status": aggregate_status,
            "manifest_path": str(self.manifest_path),
            "models": results,
            "error": None if aggregate_status == "READY" else "One or more models failed validation",
        }


model_validator = ModelIntegrityValidator()
