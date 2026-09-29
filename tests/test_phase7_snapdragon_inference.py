"""
Smart Spectator - Phase 7 Snapdragon & Hardware Inference Tests
Conforms to Sections 44, 46, 47, 58, 59, 62 of Phase 7 Master Specification.
Tests provider detection, fallback degradation, model checksum verification, and release artifacts.
"""

import hashlib
import json
from pathlib import Path
import pytest
import numpy as np

from ai.inference.manager import provider_manager, HardwareBackend
from ai.models.predictor import SpectatorNetPredictor


def test_hardware_provider_detection_and_fallback_chain():
    """
    Verifies that the inference provider manager accurately discovers available backends
    and enforces the fallback chain without crashing (Sections 47, 62).
    """
    backends = provider_manager.detect_available_backends()
    assert len(backends) >= 1
    # Universal fallback CPU must always be available
    assert HardwareBackend.CPU in backends

    # Request auto-selection: must resolve to highest tier available
    backend, provider = provider_manager.get_preferred_provider("auto")
    assert backend in backends
    assert provider is not None

    # Explicit request for CPU must succeed
    cpu_b, cpu_p = provider_manager.get_preferred_provider("cpu")
    assert cpu_b == HardwareBackend.CPU
    assert cpu_p.backend == HardwareBackend.CPU

    # Load model with automatic graceful degradation
    b, p, success = provider_manager.load_model_with_fallback(
        model_id="spectatornet_test",
        model_path="ai/models/spectatornet.onnx",
        requested="auto",
    )
    assert success is True
    assert p is not None


def test_release_model_artifacts_and_manifest():
    """Verifies that release model artifacts and manifest.json exist with valid metadata (Section 58)."""
    manifest_path = Path("ai/models/releases/manifest.json")
    assert manifest_path.exists(), "Release manifest.json is missing!"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "spectatornet_v1.onnx" in manifest
    assert "spectatornet_v1_int8.onnx" in manifest
    assert "detector_v1.onnx" in manifest

    for name, meta in manifest.items():
        assert meta["model_version"] == "1.0.0"
        assert "sha256" in meta and len(meta["sha256"]) == 64
        assert meta["size_bytes"] > 0
        model_file = Path("ai/models/releases") / name
        assert model_file.exists()


def test_model_checksum_verification():
    """Verifies that on-disk release models match their recorded SHA-256 hashes (Section 59)."""
    manifest_path = Path("ai/models/releases/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for name, meta in manifest.items():
        model_path = Path("ai/models/releases") / name
        actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        assert actual_hash == meta["sha256"], f"Checksum mismatch for release model '{name}'!"


def test_spectatornet_int8_quantized_inference():
    """Verifies that quantized INT8 SpectatorNet executes cleanly and outputs 9 event class probabilities."""
    int8_path = Path("ai/models/spectatornet_int8.onnx")
    assert int8_path.exists()

    predictor = SpectatorNetPredictor(
        model_path=str(int8_path),
        normalization_path="ai/datasets/smart_spectator/statistics/normalization.json",
    )
    assert predictor.session is not None

    # Dummy feature window (30 frames, 166 features)
    features = np.random.randn(30, 166).astype(np.float32)
    input_feed = {"temporal_features": features[np.newaxis, ...]}
    outputs = predictor.session.run(None, input_feed)

    logits = outputs[0]
    assert logits.shape == (1, 9)
    assert not np.isnan(logits).any()
