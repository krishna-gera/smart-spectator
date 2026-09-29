"""
Smart Spectator - Temporal Sequence Window Builder
Slices continuous observation streams into fixed-duration sliding windows.
Conforms to Section 7 of Phase 3 specification.
"""

from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import uuid

from shared.schemas.v1.models import Observation
from .schema import SequenceSample, TemporalAnnotation
from .constants import DEFAULT_SEQUENCE_LENGTH, DEFAULT_SAMPLING_RATE_FPS


class SequenceBuilder:
    """
    Constructs fixed-length temporal window samples from continuous streams of observations.
    Supports sliding window stride, temporal alignment, and annotation attachment.
    """

    def __init__(
        self,
        sequence_length: int = DEFAULT_SEQUENCE_LENGTH,
        fps: float = DEFAULT_SAMPLING_RATE_FPS,
        stride: int = 15,  # Stride in frames
    ):
        self.sequence_length = sequence_length
        self.fps = fps
        self.stride = stride

    def build_windows(
        self,
        observations: List[Observation],
        session_id: str,
        camera_id: str,
        source_type: str = "recorded",
        annotation: Optional[TemporalAnnotation] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SequenceSample]:
        """
        Slices an ordered list of observations into multiple overlapping SequenceSamples.
        """
        if len(observations) < self.sequence_length:
            return []

        samples: List[SequenceSample] = []
        n_obs = len(observations)

        for start_idx in range(0, n_obs - self.sequence_length + 1, self.stride):
            end_idx = start_idx + self.sequence_length
            window = observations[start_idx:end_idx]

            sample_id = f"sample_{session_id}_{start_idx}_{end_idx}_{uuid.uuid4().hex[:6]}"
            sample = SequenceSample(
                sample_id=sample_id,
                session_id=session_id,
                camera_id=camera_id,
                source_type=source_type,
                sequence_length=self.sequence_length,
                fps=self.fps,
                start_timestamp=window[0].timestamp,
                end_timestamp=window[-1].timestamp,
                observations=window,
                annotation=annotation,
                metadata=metadata or {},
            )
            samples.append(sample)

        return samples
