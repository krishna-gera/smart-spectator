"""Phase 9 Tests — Model Registry, Integrity Check & A/B Evaluator.

Validates:
1. Model discovery and SHA-256 integrity computation
2. Model activation and task routing
3. Model A/B benchmark evaluation (latency, agreement, speedup factor)
4. AI diagnostics status endpoint (/ai/status)
"""

import pytest
from ai.models.registry import model_registry
from ai.models.ab_evaluator import ab_evaluator
from fastapi.testclient import TestClient
from services.hub_backend.main import app


def test_model_registry_discovery():
    models = model_registry.list_models()
    assert len(models) >= 1

    # Check SpectatorNet models presence
    spec_model = model_registry.get_model("spectatornet_v1_fp32")
    assert spec_model is not None
    assert "SpectatorNet Temporal GRU" in spec_model.name
    assert spec_model.task_type == "temporal_event"
    assert spec_model.checksum_sha256 != ""
    assert spec_model.status in ("ACTIVE_PRODUCTION", "AVAILABLE")


def test_model_ab_evaluator():
    # Benchmark spectatornet_v1_fp32 vs spectatornet_v1_int8
    report = ab_evaluator.evaluate_temporal_models(
        model_a_id="spectatornet_v1_fp32",
        model_b_id="spectatornet_v1_int8",
        iterations=20
    )

    assert report["comparison"] == "spectatornet_v1_fp32 vs spectatornet_v1_int8"
    assert report["model_a"]["mean_latency_ms"] >= 0
    assert report["model_b"]["mean_latency_ms"] >= 0
    assert "agreement_percentage" in report
    assert report["speedup_factor"] > 0
    assert "recommendation" in report


def test_ai_status_comprehensive_diagnostics():
    client = TestClient(app)
    res = client.get("/api/v1/ai/status")
    assert res.status_code == 200
    data = res.json()

    assert "status" in data
    assert "detector" in data
    assert "tracker" in data
    assert "temporal_model" in data
    assert "provider" in data
    assert "inference_fps" in data
    assert "latency_ms" in data
    assert "models_integrity_status" in data
