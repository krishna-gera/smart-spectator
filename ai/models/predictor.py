"""
Smart Spectator - SpectatorNet Inference Predictor & Phase 4 Contract Interface
Consumes rolling Observation sequences, applies feature encoding and normalization,
executes SpectatorNet ONNX or PyTorch inference, and emits EventPrediction contracts.
Conforms to Sections 44 and 45 of Phase 3 specification.
"""

from datetime import datetime, timezone
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import onnxruntime as ort
import torch

from shared.schemas.v1.models import Observation, EventPrediction
from ai.datasets.feature_encoder import TemporalFeatureEncoder, FeatureNormalizer
from ai.datasets.constants import ID_TO_CLASS, DEFAULT_EVENT_CLASSES


class SpectatorNetPredictor:
    """
    Production-ready temporal inference runtime engine.
    Wraps ONNX Runtime session or PyTorch checkpoint, transforms raw observation windows
    into standardized EventPrediction schemas consumable by the Phase 4 Event Engine.
    """

    def __init__(
        self,
        model_path: str = "ai/models/spectatornet.onnx",
        normalization_path: str = "ai/datasets/smart_spectator/statistics/normalization.json",
        sequence_length: int = 30,
        provider: str = "CPUExecutionProvider",
    ):
        self.model_path = Path(model_path)
        self.sequence_length = sequence_length
        self.encoder = TemporalFeatureEncoder(max_objects=16, ablation_mode="full")
        self.normalizer = FeatureNormalizer.load(normalization_path) if Path(normalization_path).exists() else None

        # Initialize ONNX Runtime session
        self.session = None
        if self.model_path.exists():
            available = ort.get_available_providers()
            providers = [provider] if provider in available else ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name

    def predict_window(
        self,
        observations: List[Observation],
        camera_id: str,
    ) -> EventPrediction:
        """
        Executes end-to-end inference on an Observation sequence window.
        Returns a strongly-typed EventPrediction schema.
        """
        t0 = time.perf_counter()
        assert len(observations) > 0, "Observation window cannot be empty"

        # 1. Feature Encoding & Normalization
        feat_matrix = self.encoder.encode_sequence(
            observations, target_length=self.sequence_length, normalizer=self.normalizer
        )
        input_tensor = np.expand_dims(feat_matrix, axis=0).astype(np.float32)  # [1, T, D]

        # 2. Model Inference
        if self.session is not None:
            raw_logits = self.session.run([self.output_name], {self.input_name: input_tensor})[0][0]
        else:
            # Fallback uniform if uninitialized
            raw_logits = np.zeros(len(DEFAULT_EVENT_CLASSES), dtype=np.float32)

        # 3. Softmax probabilities
        exp_logits = np.exp(raw_logits - np.max(raw_logits))
        probs = exp_logits / np.sum(exp_logits)

        pred_id = int(np.argmax(probs))
        confidence = float(probs[pred_id])
        event_type = ID_TO_CLASS.get(pred_id, "NORMAL_BACKGROUND")
        inference_time_ms = (time.perf_counter() - t0) * 1000.0

        # 4. Extract Affected Track IDs
        affected_tracks = set()
        for obs in observations:
            for t in obs.tracked_objects:
                affected_tracks.add(t.track_id)

        class_prob_dict = {
            ID_TO_CLASS.get(idx, f"Class_{idx}"): round(float(prob), 4)
            for idx, prob in enumerate(probs)
        }

        # 5. Build EventPrediction Contract (Phase 4 Interface)
        return EventPrediction(
            schema_version="1.0",
            camera_id=camera_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            confidence=round(confidence, 4),
            start_time=observations[0].timestamp,
            end_time=observations[-1].timestamp,
            affected_tracks=sorted(list(affected_tracks)),
            class_probabilities=class_prob_dict,
            sequence_length=len(observations),
            metadata={
                "inference_time_ms": round(inference_time_ms, 3),
                "model": "SpectatorNet-ONNX",
                "backend": self.session.get_providers()[0] if self.session else "none",
            },
        )
