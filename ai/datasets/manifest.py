"""
Smart Spectator - Dataset Manifest Manager
Handles writing and parsing of train.jsonl, val.jsonl, and test.jsonl manifests.
Conforms to Section 13 of Phase 3 specification.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .schema import SequenceSample, ManifestEntry, DatasetMetadata
from .constants import CLASS_TO_ID


class ManifestManager:
    """Manages manifest serialization, reading, and dataset versioning."""

    @staticmethod
    def sample_to_manifest_entry(sample: SequenceSample, split: str, sequence_path: str) -> ManifestEntry:
        label = sample.annotation.label if sample.annotation else "NORMAL_BACKGROUND"
        label_id = sample.annotation.label_id if sample.annotation else CLASS_TO_ID.get(label, 0)

        return ManifestEntry(
            sample_id=sample.sample_id,
            session_id=sample.session_id,
            dataset_version="v1",
            camera_id=sample.camera_id,
            source_type=sample.source_type,
            sequence_path=sequence_path,
            start_timestamp=sample.start_timestamp.isoformat(),
            end_timestamp=sample.end_timestamp.isoformat(),
            fps=sample.fps,
            sequence_length=sample.sequence_length,
            label=label,
            label_id=label_id,
            split=split,
            metadata=sample.metadata,
        )

    @staticmethod
    def write_manifest(entries: List[ManifestEntry], output_file: str):
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            for entry in entries:
                f.write(entry.model_dump_json() + "\n")

    @staticmethod
    def load_manifest(manifest_file: str) -> List[ManifestEntry]:
        entries: List[ManifestEntry] = []
        with open(manifest_file, "r") as f:
            for line in f:
                if line.strip():
                    entries.append(ManifestEntry.model_validate_json(line.strip()))
        return entries
