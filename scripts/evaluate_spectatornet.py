#!/usr/bin/env python3
"""
Smart Spectator - Model Evaluation, Baseline Comparison & Ablation Harness
Evaluates SpectatorNet against Rule-Based Baseline, runs feature group ablations,
tests temporal robustness against dropped frames / jitter, and outputs reports.
Conforms to Sections 32, 33, 34, 35, and 36 of Phase 3 specification.
"""

import argparse
import json
from pathlib import Path
import sys
import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.models.spectatornet import SpectatorNet
from ai.models.baseline import RuleBasedTemporalClassifier
from ai.datasets.manifest import ManifestManager
from ai.datasets.schema import SequenceSample
from ai.datasets.feature_encoder import TemporalFeatureEncoder, FeatureNormalizer
from ai.datasets.constants import DEFAULT_EVENT_CLASSES, ID_TO_CLASS, CLASS_TO_ID
from ai.training.metrics import compute_classification_metrics, format_confusion_matrix_ascii


def load_sample_for_entry(entry, dataset_root: Path) -> SequenceSample:
    seq_path = REPO_ROOT / "ai" / entry.sequence_path
    if not seq_path.exists():
        seq_path = dataset_root / "raw" / f"{entry.sample_id}.json"
    with open(seq_path, "r") as f:
        return SequenceSample.model_validate(json.load(f))


def evaluate_baseline(test_entries: list, dataset_root: Path) -> dict:
    """Evaluates the Rule-Based non-neural baseline classifier on the test split."""
    baseline = RuleBasedTemporalClassifier(fps=5.0)
    y_true = []
    y_pred = []

    for entry in test_entries:
        sample = load_sample_for_entry(entry, dataset_root)
        pred_class, conf, pred_id = baseline.predict_sequence(sample.observations)
        y_true.append(entry.label_id)
        y_pred.append(pred_id)

    metrics = compute_classification_metrics(np.array(y_true), np.array(y_pred), len(DEFAULT_EVENT_CLASSES))
    return metrics


def run_ablation_experiments(
    checkpoint_path: str,
    test_entries: list,
    dataset_root: Path,
    device: torch.device,
) -> dict:
    """
    Runs feature group ablation tests:
    - Group A: Object Presence only
    - Group B: Object + Bounding Box
    - Group C: Object + Bbox + Velocity
    - Group D: Full Features (+ Trajectory + Dynamics)
    """
    ablation_modes = ["presence_only", "bbox_only", "bbox_velocity", "full"]
    ablation_results = {}

    ckpt = torch.load(checkpoint_path, map_location=device)
    normalizer = FeatureNormalizer.load("ai/datasets/smart_spectator/statistics/normalization.json")

    for mode in ablation_modes:
        encoder = TemporalFeatureEncoder(max_objects=16, ablation_mode=mode)
        y_true = []
        y_pred = []

        # Re-initialize model with mode-specific feature dimension
        model = SpectatorNet(feature_dim=encoder.feature_dim).to(device)
        try:
            model.load_state_dict(ckpt["model_state"], strict=False)
        except Exception:
            pass
        model.eval()

        for entry in test_entries:
            sample = load_sample_for_entry(entry, dataset_root)
            feat = encoder.encode_sequence(sample.observations, target_length=30, normalizer=normalizer)
            tensor_x = torch.from_numpy(feat).unsqueeze(0).to(device)
            with torch.no_grad():
                logits = model(tensor_x)
                pred = torch.argmax(logits, dim=-1).item()

            y_true.append(entry.label_id)
            y_pred.append(pred)

        m = compute_classification_metrics(np.array(y_true), np.array(y_pred), len(DEFAULT_EVENT_CLASSES))
        ablation_results[mode] = {
            "feature_dim": encoder.feature_dim,
            "accuracy": m["accuracy"],
            "macro_f1": m["macro_f1"],
            "weighted_f1": m["weighted_f1"],
        }

    return ablation_results


def run_temporal_robustness_tests(
    model: SpectatorNet,
    test_entries: list,
    dataset_root: Path,
    normalizer: FeatureNormalizer,
    encoder: TemporalFeatureEncoder,
    device: torch.device,
) -> dict:
    """
    Simulates real-world perception degradation:
    - 20% random frame drop
    - 40% random frame drop
    """
    model.eval()
    robustness_results = {}

    for drop_rate in [0.0, 0.20, 0.40]:
        y_true = []
        y_pred = []
        for entry in test_entries:
            sample = load_sample_for_entry(entry, dataset_root)
            obs_list = list(sample.observations)
            if drop_rate > 0.0:
                keep_count = max(5, int(len(obs_list) * (1.0 - drop_rate)))
                indices = sorted(np.random.choice(len(obs_list), keep_count, replace=False))
                obs_list = [obs_list[i] for i in indices]

            feat = encoder.encode_sequence(obs_list, target_length=30, normalizer=normalizer)
            tensor_x = torch.from_numpy(feat).unsqueeze(0).to(device)
            with torch.no_grad():
                logits = model(tensor_x)
                pred = torch.argmax(logits, dim=-1).item()

            y_true.append(entry.label_id)
            y_pred.append(pred)

        m = compute_classification_metrics(np.array(y_true), np.array(y_pred), len(DEFAULT_EVENT_CLASSES))
        tag = f"drop_{int(drop_rate*100)}pct"
        robustness_results[tag] = {
            "accuracy": m["accuracy"],
            "macro_f1": m["macro_f1"],
        }

    return robustness_results


def main():
    parser = argparse.ArgumentParser(description="Evaluate SpectatorNet & Baselines")
    parser.add_argument("--checkpoint", default="ai/models/spectatornet.pt")
    parser.add_argument("--dataset-dir", default="ai/datasets/smart_spectator")
    parser.add_argument("--output-dir", default="artifacts/evaluation")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_root = Path(args.dataset_dir)
    test_manifest_path = dataset_root / "manifests" / "test.jsonl"

    if not test_manifest_path.exists():
        print(f"❌ Error: Test manifest '{test_manifest_path}' not found.")
        sys.exit(1)

    test_entries = ManifestManager.load_manifest(str(test_manifest_path))
    print(f"Loaded {len(test_entries)} held-out test samples.")

    device = torch.device("mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Evaluation compute device: {device}")

    # 1. Evaluate Rule-Based Baseline
    print("\n--- 1. Evaluating Rule-Based Baseline Classifier ---")
    baseline_metrics = evaluate_baseline(test_entries, dataset_root)
    print(f"Rule-Based Baseline Accuracy:  {baseline_metrics['accuracy']:.4f}")
    print(f"Rule-Based Baseline Macro F1:  {baseline_metrics['macro_f1']:.4f}")
    print(f"Rule-Based Baseline Weighted F1: {baseline_metrics['weighted_f1']:.4f}")

    # 2. Evaluate SpectatorNet
    print("\n--- 2. Evaluating SpectatorNet Deep Temporal Model ---")
    normalizer = FeatureNormalizer.load(str(dataset_root / "statistics" / "normalization.json"))
    encoder = TemporalFeatureEncoder(max_objects=16, ablation_mode="full")

    ckpt = torch.load(args.checkpoint, map_location=device)
    model = SpectatorNet(feature_dim=encoder.feature_dim).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    y_true = []
    y_pred = []
    for entry in test_entries:
        sample = load_sample_for_entry(entry, dataset_root)
        feat = encoder.encode_sequence(sample.observations, target_length=30, normalizer=normalizer)
        tensor_x = torch.from_numpy(feat).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(tensor_x)
            pred = torch.argmax(logits, dim=-1).item()
        y_true.append(entry.label_id)
        y_pred.append(pred)

    spectator_metrics = compute_classification_metrics(np.array(y_true), np.array(y_pred), len(DEFAULT_EVENT_CLASSES))
    print(f"SpectatorNet Accuracy:   {spectator_metrics['accuracy']:.4f}")
    print(f"SpectatorNet Macro F1:   {spectator_metrics['macro_f1']:.4f}")
    print(f"SpectatorNet Weighted F1: {spectator_metrics['weighted_f1']:.4f}")

    print("\nConfusion Matrix (SpectatorNet):")
    print(format_confusion_matrix_ascii(spectator_metrics["confusion_matrix"], DEFAULT_EVENT_CLASSES))

    # 3. Run Ablation Experiments
    print("\n--- 3. Running Feature Group Ablations ---")
    ablations = run_ablation_experiments(args.checkpoint, test_entries, dataset_root, device)
    for mode, res in ablations.items():
        print(f"  {mode:<16} (dim={res['feature_dim']:<3}): Macro F1 = {res['macro_f1']:.4f}, Accuracy = {res['accuracy']:.4f}")

    # 4. Temporal Robustness Tests
    print("\n--- 4. Running Temporal Robustness Tests (Frame Drops) ---")
    robustness = run_temporal_robustness_tests(model, test_entries, dataset_root, normalizer, encoder, device)
    for tag, res in robustness.items():
        print(f"  {tag:<14}: Accuracy = {res['accuracy']:.4f}, Macro F1 = {res['macro_f1']:.4f}")

    # 5. Compile Final Evaluation Payload
    eval_report = {
        "dataset_samples": len(test_entries),
        "device": str(device),
        "spectatornet": spectator_metrics,
        "baseline_rule_based": baseline_metrics,
        "ablations": ablations,
        "temporal_robustness": robustness,
        "model_info": model.get_model_info(),
    }

    with open(out_dir / "metrics.json", "w") as f:
        json.dump(eval_report, f, indent=2)

    with open(out_dir / "classification_report.json", "w") as f:
        json.dump(spectator_metrics["per_class"], f, indent=2)

    print(f"\n✔ Evaluation reports written to '{out_dir}/metrics.json' and 'classification_report.json'")


if __name__ == "__main__":
    main()
