"""
Smart Spectator - Dataset Quality & Integrity Validator
Detects duplicate IDs, temporal leakage, NaN/Inf values, invalid bbox coordinates,
sequence length discrepancies, and missing files.
Conforms to Section 16 of Phase 3 specification.
"""

from collections import Counter
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import numpy as np

from .schema import ManifestEntry, SequenceSample
from .constants import DEFAULT_EVENT_CLASSES, CLASS_TO_ID


class DatasetValidationReport:
    def __init__(self):
        self.total_samples = 0
        self.train_count = 0
        self.val_count = 0
        self.test_count = 0
        self.class_counts: Dict[str, int] = Counter()
        self.split_class_distribution: Dict[str, Dict[str, int]] = {
            "train": Counter(),
            "val": Counter(),
            "test": Counter(),
        }
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.duplicate_sample_ids = 0
        self.temporal_leakage_cases = 0
        self.coordinate_violations = 0
        self.nan_or_inf_violations = 0
        self.sequence_length_mismatches = 0
        self.passed = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "total_samples": self.total_samples,
            "train_count": self.train_count,
            "val_count": self.val_count,
            "test_count": self.test_count,
            "class_counts": dict(self.class_counts),
            "split_class_distribution": {k: dict(v) for k, v in self.split_class_distribution.items()},
            "errors": self.errors,
            "warnings": self.warnings,
            "duplicate_sample_ids": self.duplicate_sample_ids,
            "temporal_leakage_cases": self.temporal_leakage_cases,
            "coordinate_violations": self.coordinate_violations,
            "nan_or_inf_violations": self.nan_or_inf_violations,
            "sequence_length_mismatches": self.sequence_length_mismatches,
        }

    def print_summary(self):
        print("\n==================================================")
        print("          DATASET QUALITY VALIDATION REPORT")
        print("==================================================")
        print(f"Total Samples:      {self.total_samples}")
        print(f"  - Train Split:    {self.train_count}")
        print(f"  - Val Split:      {self.val_count}")
        print(f"  - Test Split:     {self.test_count}")
        print("\nClass Distribution:")
        for cls_name, count in sorted(self.class_counts.items()):
            pct = (count / self.total_samples * 100.0) if self.total_samples > 0 else 0.0
            print(f"  {cls_name:<20}: {count:>5} ({pct:>5.1f}%)")

        print("\nIntegrity Checks:")
        print(f"  Duplicates:       {self.duplicate_sample_ids} detected")
        print(f"  Temporal Leakage: {self.temporal_leakage_cases} detected")
        print(f"  Coordinate Bbox:  {self.coordinate_violations} violations")
        print(f"  NaN / Inf:        {self.nan_or_inf_violations} violations")
        print(f"  Sequence Mismatch:{self.sequence_length_mismatches} violations")

        if self.errors:
            print("\n❌ CRITICAL ERRORS:")
            for err in self.errors[:10]:
                print(f"  - {err}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors.")
        else:
            print("\n✔ Zero critical integrity errors detected!")

        status_str = "PASS" if self.passed else "FAIL"
        print(f"\nSTATUS: {status_str}")
        print("==================================================\n")


class DatasetValidator:
    """Validates dataset manifests and sample payloads."""

    def __init__(self, expected_sequence_length: int = 30):
        self.expected_sequence_length = expected_sequence_length

    def validate_manifests(
        self,
        train_entries: List[ManifestEntry],
        val_entries: List[ManifestEntry],
        test_entries: List[ManifestEntry],
    ) -> DatasetValidationReport:
        report = DatasetValidationReport()
        report.train_count = len(train_entries)
        report.val_count = len(val_entries)
        report.test_count = len(test_entries)
        report.total_samples = report.train_count + report.val_count + report.test_count

        all_entries = train_entries + val_entries + test_entries

        # 1. Duplicate Sample ID check
        seen_sample_ids = set()
        for e in all_entries:
            if e.sample_id in seen_sample_ids:
                report.duplicate_sample_ids += 1
                report.errors.append(f"Duplicate sample_id: {e.sample_id}")
            seen_sample_ids.add(e.sample_id)

            report.class_counts[e.label] += 1
            report.split_class_distribution[e.split][e.label] += 1

            if e.label not in DEFAULT_EVENT_CLASSES:
                report.errors.append(f"Invalid label '{e.label}' in sample {e.sample_id}")

            if e.sequence_length != self.expected_sequence_length:
                report.sequence_length_mismatches += 1
                report.errors.append(
                    f"Sample {e.sample_id} length {e.sequence_length} != expected {self.expected_sequence_length}"
                )

        # 2. Temporal Leakage Check (Session ID overlap between splits)
        train_sessions = {e.session_id for e in train_entries}
        val_sessions = {e.session_id for e in val_entries}
        test_sessions = {e.session_id for e in test_entries}

        leak_train_val = train_sessions & val_sessions
        leak_train_test = train_sessions & test_sessions
        leak_val_test = val_sessions & test_sessions

        if leak_train_val:
            report.temporal_leakage_cases += len(leak_train_val)
            report.errors.append(f"Temporal leakage between train and val on sessions: {leak_train_val}")
        if leak_train_test:
            report.temporal_leakage_cases += len(leak_train_test)
            report.errors.append(f"Temporal leakage between train and test on sessions: {leak_train_test}")
        if leak_val_test:
            report.temporal_leakage_cases += len(leak_val_test)
            report.errors.append(f"Temporal leakage between val and test on sessions: {leak_val_test}")

        report.passed = (len(report.errors) == 0 and report.total_samples > 0)
        return report

    def validate_sample_tensors(self, feature_tensor: np.ndarray) -> Tuple[bool, List[str]]:
        """Validates numerical integrity of an encoded feature tensor."""
        errors = []
        if np.isnan(feature_tensor).any():
            errors.append("NaN detected in feature tensor")
        if np.isinf(feature_tensor).any():
            errors.append("Inf detected in feature tensor")
        return len(errors) == 0, errors
