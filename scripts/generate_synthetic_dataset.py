#!/usr/bin/env python3
"""
Smart Spectator - Synthetic Dataset Generation & Ingestion Script
Generates a multi-session synthetic dataset across all 9 event classes,
computes training feature normalization, writes manifests, and validates integrity.
"""

import argparse
import json
from pathlib import Path
import sys
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.datasets.synthetic_generator import SyntheticSequenceGenerator
from ai.datasets.split import split_samples_by_session
from ai.datasets.manifest import ManifestManager
from ai.datasets.feature_encoder import TemporalFeatureEncoder, FeatureNormalizer
from ai.datasets.validator import DatasetValidator
from ai.datasets.constants import CLASS_TO_ID, DEFAULT_EVENT_CLASSES


def generate_and_save_dataset(
    output_dir: str = "ai/datasets/smart_spectator",
    samples_per_class: int = 20,
    num_sessions: int = 10,
    seed: int = 42,
):
    print("==================================================")
    print(" SMART SPECTATOR — DATASET GENERATION PIPELINE")
    print("==================================================")
    print(f"Target Output:      {output_dir}")
    print(f"Samples per class:  {samples_per_class} (Total: {samples_per_class * len(DEFAULT_EVENT_CLASSES)})")
    print(f"Sessions:           {num_sessions}")
    print(f"Random Seed:        {seed}")

    base_path = Path(output_dir)
    raw_dir = base_path / "raw"
    processed_dir = base_path / "processed"
    manifests_dir = base_path / "manifests"
    stats_dir = base_path / "statistics"
    versions_dir = base_path / "versions"

    for d in [raw_dir, processed_dir, manifests_dir, stats_dir, versions_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 1. Generate Samples
    print("\n[Step 1] Generating synthetic observation sequences...")
    gen = SyntheticSequenceGenerator(sequence_length=30, fps=5.0, seed=seed)
    samples = gen.generate_dataset(samples_per_class=samples_per_class, num_sessions=num_sessions)
    print(f"✔ Generated {len(samples)} sequence samples across {num_sessions} sessions.")

    # 2. Split by Session (Strictly Zero Leakage)
    print("\n[Step 2] Executing deterministic session-based train/val/test split...")
    train_samples, val_samples, test_samples = split_samples_by_session(
        samples, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=seed
    )
    print(f"✔ Partitioned into: Train={len(train_samples)}, Val={len(val_samples)}, Test={len(test_samples)}")

    # 3. Fit Normalization ONLY on Training Set
    print("\n[Step 3] Fitting feature normalization parameters on Train split...")
    encoder = TemporalFeatureEncoder(max_objects=16, ablation_mode="full")
    train_features = []
    for s in train_samples:
        feat = encoder.encode_sequence(s.observations, target_length=30)
        train_features.append(feat)

    train_tensor = np.stack(train_features, axis=0)  # [N_train, 30, feature_dim]
    normalizer = FeatureNormalizer()
    normalizer.fit(train_tensor)
    norm_path = stats_dir / "normalization.json"
    normalizer.save(str(norm_path))
    print(f"✔ Fitted normalizer on {train_tensor.shape} tensor (Mean & Std saved to '{norm_path}')")

    # 4. Save Processed Samples & Generate Manifest Entries
    print("\n[Step 4] Serializing samples and compiling manifests...")
    splits = [("train", train_samples), ("val", val_samples), ("test", test_samples)]

    split_manifest_entries = {}

    for split_name, split_list in splits:
        entries = []
        for sample in split_list:
            # Save raw sequence JSON
            seq_filename = f"{sample.sample_id}.json"
            seq_path = raw_dir / seq_filename
            with open(seq_path, "w") as f:
                f.write(sample.model_dump_json(indent=2))

            # Encode and save pre-computed normalized tensor
            norm_feat = encoder.encode_sequence(sample.observations, target_length=30, normalizer=normalizer)
            np_path = processed_dir / f"{sample.sample_id}.npy"
            np.save(str(np_path), norm_feat)

            entry = ManifestManager.sample_to_manifest_entry(
                sample, split=split_name, sequence_path=str(seq_path.relative_to(base_path.parent.parent))
            )
            entries.append(entry)

        split_manifest_entries[split_name] = entries
        manifest_file = manifests_dir / f"{split_name}.jsonl"
        ManifestManager.write_manifest(entries, str(manifest_file))
        print(f"✔ Wrote {len(entries)} entries to '{manifest_file}'")

    # 5. Save Feature Schema & Dataset Version Metadata
    schema_info = encoder.get_feature_schema()
    with open(stats_dir / "feature_schema.json", "w") as f:
        json.dump(schema_info, f, indent=2)

    version_meta = {
        "dataset_name": "smart_spectator",
        "dataset_version": "v1.0-synthetic",
        "total_samples": len(samples),
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "test_samples": len(test_samples),
        "sequence_length": 30,
        "fps": 5.0,
        "feature_dim": schema_info["feature_dim"],
        "num_classes": len(DEFAULT_EVENT_CLASSES),
        "classes": DEFAULT_EVENT_CLASSES,
        "split_seed": seed,
        "sources": {"synthetic": len(samples)},
    }
    with open(versions_dir / "dataset_v1.json", "w") as f:
        json.dump(version_meta, f, indent=2)

    # 6. Run Validation
    print("\n[Step 5] Running Dataset Validator...")
    validator = DatasetValidator(expected_sequence_length=30)
    report = validator.validate_manifests(
        split_manifest_entries["train"],
        split_manifest_entries["val"],
        split_manifest_entries["test"],
    )
    report.print_summary()
    assert report.passed, "Dataset generation failed validation!"
    print("✔ DATASET GENERATION & VALIDATION COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Spectator Dataset Generation Pipeline")
    parser.add_argument("--output-dir", default="ai/datasets/smart_spectator")
    parser.add_argument("--samples-per-class", type=int, default=20)
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    generate_and_save_dataset(
        output_dir=args.output_dir,
        samples_per_class=args.samples_per_class,
        num_sessions=args.sessions,
        seed=args.seed,
    )
