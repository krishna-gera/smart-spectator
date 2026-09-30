"""
Phase 10 Tests — Model Evolution, Dataset Metadata & Evaluation Pipeline
Conforms to Sections 19, 20, 21 & 37 of Phase 10 Specification.
Validates:
1. Registered model metadata, input/output tensor shapes, and checksums.
2. Dataset metadata transparency rules (real + synthetic == 100%, synthetic disclaimer).
3. Offline model evaluation pipeline execution and artifact generation.
"""

from pathlib import Path
import pytest

from ai.models.registry import model_registry
from ai.datasets.metadata import DatasetMetadata
from scripts.evaluate_model import evaluate_temporal_model


def test_model_registry_shapes_and_precision():
    models = model_registry.list_models()
    assert len(models) >= 3

    int8_model = model_registry.get_model("spectatornet_v1_int8")
    assert int8_model is not None
    assert int8_model.precision == "INT8"
    assert int8_model.input_shape == [1, 30, 166]
    assert int8_model.output_shape == [1, 9]


def test_dataset_metadata_integrity_and_disclaimer():
    # 1. Valid dataset with synthetic content
    ds = DatasetMetadata(
        name="spectatornet_benchmark_v2",
        version="2.0.0",
        source="Qualcomm AI Lab Field Rig",
        classes=["NORMAL_BACKGROUND", "PERSON_ENTERED"],
        samples=1000,
        sessions=20,
        split={"train": 0.7, "val": 0.15, "test": 0.15},
        license="Internal Proprietary",
        synthetic_percentage=80.0,
        real_percentage=20.0,
        environment="indoor_synthetic_rig",
        annotation_version="2.0",
    )
    assert ds.validate_integrity() is True
    disclaimer = ds.get_evaluation_disclaimer()
    assert "80.0% synthetic samples" in disclaimer
    assert "cannot be claimed as real-world" in disclaimer

    # 2. Invalid percentages
    bad_ds = DatasetMetadata(
        name="bad",
        version="1.0",
        source="test",
        classes=[],
        samples=10,
        sessions=1,
        split={"train": 0.5, "test": 0.5},
        license="test",
        synthetic_percentage=60.0,
        real_percentage=60.0,  # Sum = 120%
        environment="test",
        annotation_version="1.0",
    )
    with pytest.raises(ValueError, match="must equal 100%"):
        bad_ds.validate_integrity()


def test_model_evaluation_pipeline_execution(tmp_path):
    report = evaluate_temporal_model(
        model_id="spectatornet_v1_int8",
        num_samples=15,
        output_dir=tmp_path / "eval_out",
    )
    assert "MODEL_QUALITY" in report
    assert "SYSTEM_PERFORMANCE" in report
    assert report["MODEL_QUALITY"]["accuracy"] >= 0.0
    assert report["SYSTEM_PERFORMANCE"]["throughput_fps"] > 0.0
    assert (tmp_path / "eval_out" / "eval_spectatornet_v1_int8.json").exists()
