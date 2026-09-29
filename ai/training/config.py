"""
Smart Spectator - Training Configuration
Conforms to Sections 26 and 27 of Phase 3 specification.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class TrainingConfig:
    run_name: str = "spectatornet_v1"
    dataset_dir: str = "ai/datasets/smart_spectator"
    artifacts_dir: str = "artifacts/runs"
    epochs: int = 25
    batch_size: int = 16
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    early_stopping_patience: int = 8
    hidden_dim: int = 64
    num_layers: int = 2
    dropout: float = 0.2
    bidirectional: bool = True
    seed: int = 42
    use_class_weights: bool = True
    device: str = "auto"  # "auto", "cpu", "cuda", "mps"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
