"""
Smart Spectator - Phase 3 Test Suite
Tests:
- Dataset Manifest parsing and schema validation
- Duplicate detection and temporal leakage detection
- Deterministic train/val/test session splitting
- Feature encoder, normalizer, padding, and ablation modes
- Rule-based temporal baseline classifier
- SpectatorNet architecture, forward pass, and parameter count
- Training smoke test on tiny dataset
- ONNX export and numerical tolerance validation
- SpectatorNetPredictor end-to-end EventPrediction contract compliance
"""

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pytest
import torch

from shared.schemas.v1.models import Observation, Detection, TrackedObject, EventPrediction
from ai.datasets.constants import DEFAULT_EVENT_CLASSES, CLASS_TO_ID
from ai.datasets.schema import TemporalAnnotation, SequenceSample, ManifestEntry
from ai.datasets.synthetic_generator import SyntheticSequenceGenerator
from ai.datasets.split import split_samples_by_session
from ai.datasets.manifest import ManifestManager
from ai.datasets.validator import DatasetValidator
from ai.datasets.feature_encoder import TemporalFeatureEncoder, FeatureNormalizer
from ai.models.spectatornet import SpectatorNet
from ai.models.baseline import RuleBasedTemporalClassifier
from ai.models.predictor import SpectatorNetPredictor
from ai.training.metrics import compute_classification_metrics
from ai.training.losses import get_loss_function


# -----------------------------------------------------------------------------
# 1. Dataset Schemas & Synthetic Generation Tests
# -----------------------------------------------------------------------------

def test_synthetic_generator_creates_all_classes():
    """Verify synthetic generator accurately generates observation sequences for all 9 classes."""
    gen = SyntheticSequenceGenerator(sequence_length=30, fps=5.0, seed=123)
    for cls_name in DEFAULT_EVENT_CLASSES:
        sample = gen.generate_sample(cls_name, session_id="test_sess_01")
        assert sample.sequence_length == 30
        assert len(sample.observations) == 30
        assert sample.source_type == "synthetic"
        assert sample.annotation is not None
        assert sample.annotation.label == cls_name
        assert sample.annotation.label_id == CLASS_TO_ID[cls_name]


def test_deterministic_split_zero_temporal_leakage():
    """Verify session-based splitting guarantees zero session/window overlap between train, val, and test."""
    gen = SyntheticSequenceGenerator(seed=42)
    # Generate 50 samples across 10 distinct sessions
    samples = []
    for s_idx in range(10):
        sess_id = f"session_{s_idx:02d}"
        for c in DEFAULT_EVENT_CLASSES[:5]:
            samples.append(gen.generate_sample(c, session_id=sess_id))

    train, val, test = split_samples_by_session(samples, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=42)

    train_sessions = {s.session_id for s in train}
    val_sessions = {s.session_id for s in val}
    test_sessions = {s.session_id for s in test}

    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0
    # Zero temporal leakage assertion
    assert not (train_sessions & val_sessions)
    assert not (train_sessions & test_sessions)
    assert not (val_sessions & test_sessions)


def test_dataset_validator_catches_leakage_and_duplicates():
    """Verify DatasetValidator detects duplicate sample IDs and temporal leakage."""
    validator = DatasetValidator(expected_sequence_length=30)

    # 1. Normal entries
    e1 = ManifestEntry(
        sample_id="s1",
        session_id="sess_A",
        dataset_version="v1",
        camera_id="cam_01",
        source_type="synthetic",
        sequence_path="dummy.json",
        start_timestamp="2026-01-01T00:00:00",
        end_timestamp="2026-01-01T00:00:06",
        fps=5.0,
        sequence_length=30,
        label="NORMAL_BACKGROUND",
        label_id=0,
        split="train",
    )
    e2 = ManifestEntry(
        sample_id="s2",
        session_id="sess_B",
        dataset_version="v1",
        camera_id="cam_01",
        source_type="synthetic",
        sequence_path="dummy.json",
        start_timestamp="2026-01-01T00:00:00",
        end_timestamp="2026-01-01T00:00:06",
        fps=5.0,
        sequence_length=30,
        label="OBJECT_PRESENT",
        label_id=1,
        split="val",
    )
    # Valid report
    rep_valid = validator.validate_manifests([e1], [e2], [])
    assert rep_valid.passed is True
    assert rep_valid.duplicate_sample_ids == 0

    # 2. Duplicate ID test
    e_dup = e1.model_copy(update={"split": "val"})
    rep_dup = validator.validate_manifests([e1], [e_dup], [])
    assert rep_dup.passed is False
    assert rep_dup.duplicate_sample_ids == 1

    # 3. Leakage test (same session in train and test)
    e_leak = e1.model_copy(update={"sample_id": "s3", "split": "test"})
    rep_leak = validator.validate_manifests([e1], [], [e_leak])
    assert rep_leak.passed is False
    assert rep_leak.temporal_leakage_cases >= 1


# -----------------------------------------------------------------------------
# 2. Feature Encoder, Normalizer & Ablation Tests
# -----------------------------------------------------------------------------

def test_feature_encoder_shapes_and_padding():
    """Verify feature encoder vector dimension, padding, and truncation."""
    encoder = TemporalFeatureEncoder(max_objects=16, ablation_mode="full")
    assert encoder.feature_dim == 166

    gen = SyntheticSequenceGenerator(sequence_length=15)
    sample = gen.generate_sample("OBJECT_REMOVED", session_id="test_pad")

    # Sequence has 15 frames, target_length is 30 -> must be padded to 30
    feat_padded = encoder.encode_sequence(sample.observations, target_length=30)
    assert feat_padded.shape == (30, 166)
    # First 15 frames should be zeros (padding)
    assert np.all(feat_padded[:15] == 0.0)

    # Sequence of 40 frames truncated to 30
    sample_long = gen.generate_sample("OBJECT_REMOVED", session_id="test_trunc")
    sample_long.observations = sample_long.observations * 3
    feat_trunc = encoder.encode_sequence(sample_long.observations, target_length=30)
    assert feat_trunc.shape == (30, 166)


def test_feature_normalizer():
    """Verify FeatureNormalizer computes mean/std and applies z-score scaling."""
    norm = FeatureNormalizer()
    data = np.array([[[1.0, 10.0], [2.0, 20.0]], [[3.0, 30.0], [4.0, 40.0]]], dtype=np.float32)
    norm.fit(data)

    assert norm.mean is not None
    assert norm.std is not None
    assert abs(norm.mean[0] - 2.5) < 1e-4

    transformed = norm.transform(data)
    assert abs(np.mean(transformed)) < 1e-4


def test_ablation_feature_modes():
    """Verify feature encoder respects ablation masks."""
    gen = SyntheticSequenceGenerator(sequence_length=5)
    sample = gen.generate_sample("OBJECT_MOVED", session_id="ablation_sess")

    # 1. Presence only
    enc_presence = TemporalFeatureEncoder(ablation_mode="presence_only")
    vec_p = enc_presence.encode_observation(sample.observations[0])
    # Coordinates slots (indices 2..8) must be zero
    assert vec_p[2] == 0.0
    assert vec_p[6] == 0.0

    # 2. Bbox only
    enc_bbox = TemporalFeatureEncoder(ablation_mode="bbox_only")
    vec_b = enc_bbox.encode_observation(sample.observations[0])
    assert vec_b[2] != 0.0  # Center X present
    assert vec_b[6] == 0.0  # Velocity X zero

    # 3. Full
    enc_full = TemporalFeatureEncoder(ablation_mode="full")
    vec_f = enc_full.encode_observation(sample.observations[0])
    assert vec_f[2] != 0.0  # Center X
    assert vec_f[6] != 0.0  # Velocity X non-zero for moving object


# -----------------------------------------------------------------------------
# 3. Rule-Based Baseline Tests
# -----------------------------------------------------------------------------

def test_rule_based_baseline_predictions():
    """Verify rule-based baseline produces coherent predictions across representative scenarios."""
    baseline = RuleBasedTemporalClassifier(fps=5.0)
    gen = SyntheticSequenceGenerator(sequence_length=30)

    # Object Removed
    s_removed = gen.generate_sample("OBJECT_REMOVED", "sess_base")
    pred_rem, _, _ = baseline.predict_sequence(s_removed.observations)
    assert pred_rem == "OBJECT_REMOVED"

    # Person Entered
    s_entered = gen.generate_sample("PERSON_ENTERED", "sess_base")
    pred_ent, _, _ = baseline.predict_sequence(s_entered.observations)
    assert pred_ent == "PERSON_ENTERED"

    # Camera Blocked
    s_blocked = gen.generate_sample("CAMERA_BLOCKED", "sess_base")
    pred_blk, _, _ = baseline.predict_sequence(s_blocked.observations)
    assert pred_blk == "CAMERA_BLOCKED"


# -----------------------------------------------------------------------------
# 4. SpectatorNet Model & Checkpoint Tests
# -----------------------------------------------------------------------------

def test_spectatornet_forward_and_parameter_budget():
    """Verify SpectatorNet satisfies parameter budget (<5M) and output dimensions."""
    model = SpectatorNet(feature_dim=166, hidden_dim=64, num_layers=2, num_classes=9)
    info = model.get_model_info()

    assert info["total_parameters"] < 5_000_000
    assert info["estimated_fp32_size_mb"] < 15.0

    # Test forward pass with batch size 4
    x = torch.randn(4, 30, 166, dtype=torch.float32)
    logits = model(x)
    assert logits.shape == (4, 9)

    preds, probs = model.predict_proba(x)
    assert preds.shape == (4,)
    assert probs.shape == (4, 9)
    # Sum of probabilities across classes must equal 1.0
    assert torch.allclose(torch.sum(probs, dim=-1), torch.ones(4), atol=1e-5)


def test_spectatornet_tiny_training_smoke():
    """Smoke test: Verify SpectatorNet trains and reduces CrossEntropy loss on small batch."""
    model = SpectatorNet(feature_dim=166, hidden_dim=32, num_layers=1, num_classes=9)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    criterion = get_loss_function()

    x = torch.randn(8, 30, 166)
    y = torch.tensor([0, 1, 2, 3, 4, 5, 6, 7], dtype=torch.long)

    # Measure initial loss
    model.train()
    initial_loss = criterion(model(x), y).item()

    # Train for 5 iterations
    for _ in range(5):
        optimizer.zero_grad()
        loss = criterion(model(x), y)
        loss.backward()
        optimizer.step()

    final_loss = criterion(model(x), y).item()
    assert final_loss < initial_loss, "Training failed to reduce loss!"


# -----------------------------------------------------------------------------
# 5. ONNX Numerical Equivalence & Predictor Tests
# -----------------------------------------------------------------------------

def test_onnx_model_exists_and_numerical_equivalence():
    """Verify ai/models/spectatornet.onnx exists and numerically matches PyTorch checkpoint."""
    onnx_file = Path("ai/models/spectatornet.onnx")
    assert onnx_file.exists()

    ckpt_file = Path("ai/models/spectatornet.pt")
    assert ckpt_file.exists()

    from scripts.validate_spectatornet_onnx import validate_spectatornet_onnx
    passed = validate_spectatornet_onnx(
        checkpoint_path=str(ckpt_file),
        onnx_path=str(onnx_file),
        tolerance=1e-4,
    )
    assert passed is True


def test_spectatornet_predictor_emits_phase4_contract():
    """Verify SpectatorNetPredictor ingests Observations and emits valid EventPrediction."""
    predictor = SpectatorNetPredictor(
        model_path="ai/models/spectatornet.onnx",
        normalization_path="ai/datasets/smart_spectator/statistics/normalization.json",
    )
    gen = SyntheticSequenceGenerator(sequence_length=30)
    sample = gen.generate_sample("OBJECT_MOVED", session_id="pred_test")

    pred = predictor.predict_window(sample.observations, camera_id="cam_test_p4")

    assert isinstance(pred, EventPrediction)
    assert pred.schema_version == "1.0"
    assert pred.camera_id == "cam_test_p4"
    assert pred.event_type in DEFAULT_EVENT_CLASSES
    assert 0.0 <= pred.confidence <= 1.0
    assert len(pred.class_probabilities) == len(DEFAULT_EVENT_CLASSES)
    assert pred.sequence_length == 30
    assert "inference_time_ms" in pred.metadata
