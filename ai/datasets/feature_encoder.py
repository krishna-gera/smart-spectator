"""
Smart Spectator - Deterministic Temporal Feature Encoder & Normalizer
Transforms Observation timesteps into fixed-size numerical tensors.
Conforms to Sections 8, 9, 10, and 11 of Phase 3 specification.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import torch

from shared.schemas.v1.models import Observation, TrackedObject


class FeatureNormalizer:
    """Computes, stores, and applies z-score normalization on feature vectors."""

    def __init__(self, mean: Optional[np.ndarray] = None, std: Optional[np.ndarray] = None, eps: float = 1e-6):
        self.mean = mean
        self.std = std
        self.eps = eps

    def fit(self, feature_matrix: np.ndarray):
        """Fit normalization parameters strictly on the training set (N, T, D) or (N, D)."""
        flat = feature_matrix.reshape(-1, feature_matrix.shape[-1])
        self.mean = np.mean(flat, axis=0).astype(np.float32)
        self.std = np.std(flat, axis=0).astype(np.float32)
        # Avoid divide-by-zero for constant zero-padded features
        self.std[self.std < self.eps] = 1.0

    def transform(self, features: np.ndarray) -> np.ndarray:
        """Apply z-score normalization (x - mean) / std."""
        if self.mean is None or self.std is None:
            return features
        return ((features - self.mean) / (self.std + self.eps)).astype(np.float32)

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "mean": self.mean.tolist() if self.mean is not None else [],
            "std": self.std.tolist() if self.std is not None else [],
            "eps": self.eps,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str) -> "FeatureNormalizer":
        with open(path, "r") as f:
            data = json.load(f)
        mean = np.array(data["mean"], dtype=np.float32) if data["mean"] else None
        std = np.array(data["std"], dtype=np.float32) if data["std"] else None
        return cls(mean=mean, std=std, eps=data.get("eps", 1e-6))


class TemporalFeatureEncoder:
    """
    Deterministic feature encoder for Observation sequences.
    Converts variable-length tracked objects and detections into fixed-size tensors:
    [sequence_length, feature_dimension].
    """

    OBJECT_FEATURE_NAMES = [
        "class_id",
        "confidence",
        "center_x",
        "center_y",
        "width",
        "height",
        "velocity_x",
        "velocity_y",
        "speed",
        "normalized_area",
    ]
    GLOBAL_FEATURE_NAMES = [
        "object_count",
        "person_count",
        "motion_score",
        "disappeared_track_count",
        "new_track_count",
        "total_detections",
    ]

    def __init__(
        self,
        max_objects: int = 16,
        ablation_mode: str = "full",  # "full", "presence_only", "bbox_only", "bbox_velocity"
    ):
        self.max_objects = max_objects
        self.ablation_mode = ablation_mode
        self.object_features_per_slot = len(self.OBJECT_FEATURE_NAMES)
        self.global_features_count = len(self.GLOBAL_FEATURE_NAMES)
        self.feature_dim = (self.max_objects * self.object_features_per_slot) + self.global_features_count

    def encode_observation(
        self,
        obs: Observation,
        prev_obs: Optional[Observation] = None,
    ) -> np.ndarray:
        """Encode a single observation timestep into a 1D float32 vector of length `feature_dim`."""
        vec = np.zeros(self.feature_dim, dtype=np.float32)

        # 1. Rank tracked objects deterministically by (confidence * area)
        objects = list(obs.tracked_objects) if obs.tracked_objects else []
        def rank_key(t: TrackedObject) -> float:
            bbox = t.current_bbox
            w = max(0.0, bbox[2] - bbox[0])
            h = max(0.0, bbox[3] - bbox[1])
            return float(t.confidence * (w * h + 1e-4))

        objects.sort(key=rank_key, reverse=True)
        top_objects = objects[: self.max_objects]

        # 2. Populate object slots
        slot_idx = 0
        person_count = 0

        for obj in top_objects:
            offset = slot_idx * self.object_features_per_slot
            bbox = obj.current_bbox
            w = max(0.0, min(1.0, bbox[2] - bbox[0]))
            h = max(0.0, min(1.0, bbox[3] - bbox[1]))
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            area = w * h

            vx = obj.velocity_vector[0] if obj.velocity_vector and len(obj.velocity_vector) > 0 else 0.0
            vy = obj.velocity_vector[1] if obj.velocity_vector and len(obj.velocity_vector) > 1 else 0.0
            speed = float(np.sqrt(vx * vx + vy * vy))

            is_person = (obj.class_name.lower() == "person")
            if is_person:
                person_count += 1

            # Map class name to numeric ID heuristic (0 for person, 1 for objects)
            class_code = 1.0 if is_person else 2.0

            if self.ablation_mode == "presence_only":
                vec[offset + 0] = class_code
                vec[offset + 1] = float(obj.confidence)
                # Other slots remain zero
            elif self.ablation_mode == "bbox_only":
                vec[offset + 0] = class_code
                vec[offset + 1] = float(obj.confidence)
                vec[offset + 2] = float(cx)
                vec[offset + 3] = float(cy)
                vec[offset + 4] = float(w)
                vec[offset + 5] = float(h)
                vec[offset + 9] = float(area)
            elif self.ablation_mode == "bbox_velocity":
                vec[offset + 0] = class_code
                vec[offset + 1] = float(obj.confidence)
                vec[offset + 2] = float(cx)
                vec[offset + 3] = float(cy)
                vec[offset + 4] = float(w)
                vec[offset + 5] = float(h)
                vec[offset + 6] = float(vx)
                vec[offset + 7] = float(vy)
                vec[offset + 8] = float(speed)
                vec[offset + 9] = float(area)
            else:  # "full"
                vec[offset + 0] = class_code
                vec[offset + 1] = float(obj.confidence)
                vec[offset + 2] = float(cx)
                vec[offset + 3] = float(cy)
                vec[offset + 4] = float(w)
                vec[offset + 5] = float(h)
                vec[offset + 6] = float(vx)
                vec[offset + 7] = float(vy)
                vec[offset + 8] = float(speed)
                vec[offset + 9] = float(area)

            slot_idx += 1

        # 3. Global Temporal / Scene Features
        global_offset = self.max_objects * self.object_features_per_slot
        curr_track_ids = {t.track_id for t in obs.tracked_objects}
        prev_track_ids = {t.track_id for t in prev_obs.tracked_objects} if prev_obs and prev_obs.tracked_objects else set()

        new_tracks = len(curr_track_ids - prev_track_ids) if prev_obs else 0
        disappeared_tracks = len(prev_track_ids - curr_track_ids) if prev_obs else 0

        # Scene motion
        motion_score = float(obs.scene_state.get("motion_detected", False)) if hasattr(obs, "scene_state") else 0.0

        vec[global_offset + 0] = float(len(obs.tracked_objects)) / float(self.max_objects)
        vec[global_offset + 1] = float(person_count) / 10.0
        vec[global_offset + 2] = motion_score
        vec[global_offset + 3] = float(disappeared_tracks) / float(self.max_objects)
        vec[global_offset + 4] = float(new_tracks) / float(self.max_objects)
        vec[global_offset + 5] = float(len(obs.detections)) / float(self.max_objects)

        return vec

    def encode_sequence(
        self,
        observations: List[Observation],
        target_length: int = 30,
        normalizer: Optional[FeatureNormalizer] = None,
    ) -> np.ndarray:
        """
        Encodes a sequence of observations into a 2D matrix:
        [target_length, feature_dim].
        Handles temporal padding if fewer observations exist, or slicing if more.
        """
        feats: List[np.ndarray] = []
        prev: Optional[Observation] = None

        for obs in observations:
            feat = self.encode_observation(obs, prev)
            feats.append(feat)
            prev = obs

        # Truncate or Pad to target_length
        if len(feats) > target_length:
            feats = feats[-target_length:]
        elif len(feats) < target_length:
            pad_count = target_length - len(feats)
            pad_feats = [np.zeros(self.feature_dim, dtype=np.float32) for _ in range(pad_count)]
            # Prepend padding so recent timesteps are at the end
            feats = pad_feats + feats

        mat = np.stack(feats, axis=0)  # [target_length, feature_dim]
        if normalizer:
            mat = normalizer.transform(mat)
        return mat.astype(np.float32)

    def get_feature_schema(self) -> Dict[str, Any]:
        """Returns structured metadata about the feature vector layout."""
        return {
            "feature_dim": self.feature_dim,
            "max_objects": self.max_objects,
            "ablation_mode": self.ablation_mode,
            "object_slot_dim": self.object_features_per_slot,
            "global_dim": self.global_features_count,
            "object_features": self.OBJECT_FEATURE_NAMES,
            "global_features": self.GLOBAL_FEATURE_NAMES,
        }
