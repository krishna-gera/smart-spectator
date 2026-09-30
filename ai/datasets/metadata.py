"""
Smart Spectator - Dataset Versioning & Provenance Metadata
Conforms to Sections 20 & 22 of Phase 10 Specification.
Tracks dataset composition, synthetic vs real split, and licensing.
Strictly prohibits claiming synthetic validation as real-world accuracy.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class DatasetMetadata:
    name: str
    version: str
    source: str
    classes: List[str]
    samples: int
    sessions: int
    split: Dict[str, float]  # {"train": 0.70, "val": 0.15, "test": 0.15}
    license: str
    synthetic_percentage: float  # e.g., 85.0
    real_percentage: float  # e.g., 15.0
    environment: str  # "indoor_synthetic_rig", "field_trial_lab"
    annotation_version: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate_integrity(self) -> bool:
        """Validates that real + synthetic sum to 100% and split ratios are valid."""
        total_pct = self.synthetic_percentage + self.real_percentage
        if abs(total_pct - 100.0) > 0.1:
            raise ValueError(f"Synthetic ({self.synthetic_percentage}%) + Real ({self.real_percentage}%) must equal 100%.")
        split_sum = sum(self.split.values())
        if abs(split_sum - 1.0) > 0.01:
            raise ValueError(f"Split ratios must sum to 1.0; got {split_sum}")
        return True

    def get_evaluation_disclaimer(self) -> str:
        """Returns required transparency disclaimer regarding validation composition."""
        if self.synthetic_percentage > 0.0:
            return (
                f"NOTICE: Dataset '{self.name}:{self.version}' contains {self.synthetic_percentage}% synthetic samples. "
                "Synthetic validation metrics cannot be claimed as real-world field accuracy."
            )
        return "Dataset consists of 100% validated real-world field capture."

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
