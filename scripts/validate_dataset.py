#!/usr/bin/env python3
"""
Smart Spectator - Dataset Validation Script
Validates dataset integrity, checks for temporal leakage, duplicates, NaN/Inf,
and outputs human-readable report. Exits with non-zero status on error.
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.datasets.manifest import ManifestManager
from ai.datasets.validator import DatasetValidator


def main():
    parser = argparse.ArgumentParser(description="Smart Spectator Dataset Validator")
    parser.add_argument(
        "--dataset-dir",
        default="ai/datasets/smart_spectator",
        help="Root directory of the dataset",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset_dir)
    manifest_dir = dataset_path / "manifests"

    train_path = manifest_dir / "train.jsonl"
    val_path = manifest_dir / "val.jsonl"
    test_path = manifest_dir / "test.jsonl"

    if not train_path.exists() or not val_path.exists() or not test_path.exists():
        print(f"❌ Error: Missing manifest files in '{manifest_dir}'.")
        print("Please ensure train.jsonl, val.jsonl, and test.jsonl are generated.")
        sys.exit(1)

    train_entries = ManifestManager.load_manifest(str(train_path))
    val_entries = ManifestManager.load_manifest(str(val_path))
    test_entries = ManifestManager.load_manifest(str(test_path))

    validator = DatasetValidator(expected_sequence_length=30)
    report = validator.validate_manifests(train_entries, val_entries, test_entries)
    report.print_summary()

    if not report.passed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
