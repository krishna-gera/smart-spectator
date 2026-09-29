"""
Smart Spectator - Dataset & Annotation Schemas
Conforms strictly to Phase 3 data specifications.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from shared.schemas.v1.models import Observation


class TemporalAnnotation(BaseModel):
    """Ground truth annotation for a temporal sequence window."""
    sample_id: str
    label: str
    label_id: int
    start_frame: int
    end_frame: int
    event_start_frame: Optional[int] = None
    event_end_frame: Optional[int] = None
    confidence: float = 1.0
    annotator: str = "system"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SequenceSample(BaseModel):
    """
    A single temporal sample containing an ordered sequence of observations
    and ground truth label.
    """
    sample_id: str
    session_id: str
    camera_id: str
    source_type: str = "synthetic"  # "synthetic", "public", "recorded"
    sequence_length: int = 30
    fps: float = 5.0
    start_timestamp: datetime
    end_timestamp: datetime
    observations: List[Observation]
    annotation: Optional[TemporalAnnotation] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ManifestEntry(BaseModel):
    """Manifest record indexing a temporal sample in the dataset."""
    sample_id: str
    session_id: str
    dataset_version: str = "v1"
    camera_id: str
    source_type: str
    sequence_path: str
    start_timestamp: str
    end_timestamp: str
    fps: float
    sequence_length: int
    label: str
    label_id: int
    split: str  # "train", "val", "test"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DatasetMetadata(BaseModel):
    """Top-level dataset version metadata for reproducibility."""
    dataset_name: str = "smart_spectator"
    dataset_version: str = "v1.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sequence_length: int = 30
    fps: float = 5.0
    max_objects_per_frame: int = 16
    feature_dim: int
    num_classes: int
    class_map: Dict[str, int]
    split_seed: int = 42
    total_samples: int
    train_count: int
    val_count: int
    test_count: int
    source_breakdown: Dict[str, int] = Field(default_factory=dict)
    class_distribution: Dict[str, Dict[str, int]] = Field(default_factory=dict)
