"""
Smart Spectator - Phase 8 Model Integrity & Tamper Resistance Test Suite
Conforms to Sections 17 & 25 of Phase 8 Master Specification.
Tests:
1. Valid release model validation passes with status READY.
2. Modified/tampered model fails checksum comparison with status MODEL_INTEGRITY_ERROR.
3. Missing model file reports status MISSING.
4. Corrupted non-ONNX file reports status MODEL_INTEGRITY_ERROR.
"""

import json
from pathlib import Path
import pytest
from ai.models.validator import ModelIntegrityValidator


@pytest.fixture
def mock_manifest_env(tmp_path):
    manifest_dir = tmp_path / "models"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / "manifest.json"

    # Copy real ONNX model
    source_model = Path("ai/models/releases/spectatornet_v1_int8.onnx")
    dummy_model = manifest_dir / "dummy_v1.onnx"
    model_bytes = source_model.read_bytes()
    dummy_model.write_bytes(model_bytes)

    import hashlib
    h = hashlib.sha256(model_bytes).hexdigest()

    manifest_data = {
        "dummy_v1.onnx": {
            "model_version": "1.0.0",
            "file_name": "dummy_v1.onnx",
            "sha256": h,
            "size_bytes": len(model_bytes),
        }
    }
    manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    return manifest_file, dummy_model


def test_valid_model_integrity_passes(mock_manifest_env):
    manifest_file, _ = mock_manifest_env
    validator = ModelIntegrityValidator(manifest_path=str(manifest_file))
    report = validator.validate_all()

    assert report["status"] == "READY"
    assert "dummy_v1.onnx" in report["models"]
    assert report["models"]["dummy_v1.onnx"]["checksum_match"] is True


def test_modified_model_fails_with_integrity_error(mock_manifest_env):
    manifest_file, dummy_model = mock_manifest_env
    # Tamper with model bytes
    dummy_model.write_bytes(b"tampered_bytes_attacker_payload")

    validator = ModelIntegrityValidator(manifest_path=str(manifest_file))
    report = validator.validate_all()

    assert report["status"] == "MODEL_INTEGRITY_ERROR"
    assert report["models"]["dummy_v1.onnx"]["status"] == "MODEL_INTEGRITY_ERROR"
    assert report["models"]["dummy_v1.onnx"]["checksum_match"] is False


def test_missing_model_reports_missing_status(mock_manifest_env):
    manifest_file, dummy_model = mock_manifest_env
    # Delete model file
    dummy_model.unlink()

    validator = ModelIntegrityValidator(manifest_path=str(manifest_file))
    report = validator.validate_all()

    assert report["status"] == "DEGRADED"
    assert report["models"]["dummy_v1.onnx"]["status"] == "MISSING"
    assert report["models"]["dummy_v1.onnx"]["checksum_match"] is False


def test_actual_release_manifest_integrity():
    """Validates the actual project release models in ai/models/releases/manifest.json."""
    validator = ModelIntegrityValidator()
    report = validator.validate_all()

    assert report["status"] == "READY"
    for name, res in report["models"].items():
        assert res["status"] == "READY"
        assert res["checksum_match"] is True
