"""
Smart Spectator - Phase 8 Diagnostics, Hardware Telemetry & Provider Fallback Tests
Conforms to Sections 2, 14, 16, 21, 25 of Phase 8 Master Specification.
Tests:
1. Unified diagnostics endpoint /api/v1/system/diagnostics returning all 11 subsystems.
2. Hardware telemetry /api/v1/system/hardware adhering strictly to Section 2 schema.
3. Provider fallback chain: QNN -> DirectML/CoreML -> CPU.
4. Failure isolation: AI provider or model failure causes graceful degradation without crashing the Hub.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.hub_backend.main import app
from services.hub_backend.config import settings
from services.hub_backend.database.connection import init_database
from ai.inference.manager import provider_manager, HardwareBackend


@pytest.fixture
def diag_env(tmp_path):
    settings.DATABASE_PATH = tmp_path / "diag_test.db"
    settings.RECORDINGS_DIR = tmp_path / "diag_recs"
    settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    init_database()
    yield
    if settings.DATABASE_PATH.exists():
        settings.DATABASE_PATH.unlink()


def test_unified_diagnostics_all_11_subsystems(diag_env):
    """Verifies that GET /api/v1/system/diagnostics returns all 11 required subsystems (Section 21)."""
    client = TestClient(app)
    res = client.get("/api/v1/system/diagnostics")
    assert res.status_code == 200
    data = res.json()

    subsystems = [
        "hub",
        "database",
        "stream_engine",
        "ai_engine",
        "event_engine",
        "recorder",
        "devices",
        "websocket",
        "storage",
        "models",
        "hardware",
    ]
    for s in subsystems:
        assert s in data, f"Subsystem '{s}' missing from diagnostics response!"
        assert "status" in data[s], f"Field 'status' missing from subsystem '{s}'"
        assert data[s]["status"] in ("READY", "DEGRADED", "FAILED", "NOT_AVAILABLE", "STARTING", "healthy")


def test_hardware_endpoint_schema_conformity(diag_env):
    """Verifies that GET /api/v1/system/hardware returns the exact schema from Section 2."""
    client = TestClient(app)
    res = client.get("/api/v1/system/hardware")
    assert res.status_code == 200
    data = res.json()

    assert "os" in data
    assert "architecture" in data
    assert "processor" in data
    assert "memory_gb" in data and data["memory_gb"] > 0
    assert "accelerators" in data and isinstance(data["accelerators"], list)
    assert "onnxruntime_providers" in data and isinstance(data["onnxruntime_providers"], list)
    assert "selected_provider" in data
    assert "qnn_available" in data and isinstance(data["qnn_available"], bool)
    assert "directml_available" in data and isinstance(data["directml_available"], bool)
    assert "cpu_available" in data and isinstance(data["cpu_available"], bool)
    assert "hardware_validation_status" in data


def test_inference_provider_fallback_scenarios():
    """
    Tests Section 16 provider fallback scenarios:
    - Auto selects best available
    - Explicit CPU always succeeds
    - Graceful degradation when model is invalid
    """
    backends = provider_manager.detect_available_backends()
    assert len(backends) >= 1
    assert HardwareBackend.CPU in backends

    # Auto preference
    best_b, best_p = provider_manager.get_preferred_provider("auto")
    assert best_p is not None

    # CPU explicit
    cpu_b, cpu_p = provider_manager.get_preferred_provider("cpu")
    assert cpu_b == HardwareBackend.CPU
    assert cpu_p.backend == HardwareBackend.CPU

    # Model missing: returns success=False without crashing
    b, p, success = provider_manager.load_model_with_fallback(
        model_id="non_existent_model_id",
        model_path="ai/models/does_not_exist_anywhere.onnx",
        requested="auto"
    )
    assert success is False
    assert p is not None  # Fallback provider retained
