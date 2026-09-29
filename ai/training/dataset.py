"""
Smart Spectator - PyTorch Temporal Dataset & DataLoader
Loads Observation sequence tensors and labels for SpectatorNet training and evaluation.
Conforms to Section 11 of Phase 3 specification.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

from ai.datasets.schema import ManifestEntry
from ai.datasets.manifest import ManifestManager
from ai.datasets.feature_encoder import TemporalFeatureEncoder, FeatureNormalizer


class SpectatorNetDataset(Dataset):
    """PyTorch Dataset loading pre-computed sequence tensors or parsing raw JSON observations."""

    def __init__(
        self,
        manifest_entries: List[ManifestEntry],
        processed_dir: Optional[str] = "ai/datasets/smart_spectator/processed",
        feature_encoder: Optional[TemporalFeatureEncoder] = None,
        normalizer: Optional[FeatureNormalizer] = None,
    ):
        self.entries = manifest_entries
        self.processed_dir = Path(processed_dir) if processed_dir else None
        self.feature_encoder = feature_encoder
        self.normalizer = normalizer

    @classmethod
    def from_manifest_file(
        cls,
        manifest_path: str,
        processed_dir: Optional[str] = "ai/datasets/smart_spectator/processed",
        normalizer: Optional[FeatureNormalizer] = None,
    ) -> "SpectatorNetDataset":
        entries = ManifestManager.load_manifest(manifest_path)
        return cls(manifest_entries=entries, processed_dir=processed_dir, normalizer=normalizer)

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        entry = self.entries[idx]

        # 1. Try loading pre-computed .npy tensor for optimal speed
        if self.processed_dir:
            npy_path = self.processed_dir / f"{entry.sample_id}.npy"
            if npy_path.exists():
                feat_mat = np.load(str(npy_path)).astype(np.float32)
                tensor_x = torch.from_numpy(feat_mat)
                tensor_y = torch.tensor(entry.label_id, dtype=torch.long)
                return tensor_x, tensor_y, entry.sample_id

        # 2. Fallback: Parse raw JSON sequence
        raw_path = Path(entry.sequence_path)
        if not raw_path.exists():
            # Try prepending repo root
            raw_path = Path("ai/datasets/smart_spectator") / entry.sequence_path

        import json
        from ai.datasets.schema import SequenceSample
        with open(raw_path, "r") as f:
            data = json.load(f)
        sample = SequenceSample.model_validate(data)

        encoder = self.feature_encoder or TemporalFeatureEncoder()
        feat_mat = encoder.encode_sequence(
            sample.observations, target_length=entry.sequence_length, normalizer=self.normalizer
        )
        tensor_x = torch.from_numpy(feat_mat)
        tensor_y = torch.tensor(entry.label_id, dtype=torch.long)
        return tensor_x, tensor_y, entry.sample_id


def create_dataloader(
    dataset: SpectatorNetDataset,
    batch_size: int = 16,
    shuffle: bool = True,
    num_workers: int = 0,
) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        drop_last=False,
    )
