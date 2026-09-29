"""
Smart Spectator - Event Engine Service Integration
Wires the EventEngine to the AI Perception Pipeline and Stream Ingestion Engine.
"""

from collections import deque
import threading
import time
from typing import Dict, Optional

from shared.schemas.v1.models import Observation, EventPrediction
from ai.models.predictor import SpectatorNetPredictor
from .engine import EventEngine


class EventEngineService:
    """
    Manages the lifecycle of the EventEngine and connects it to
    the streaming and perception pipelines.
    """

    def __init__(self):
        self.engine = EventEngine()
        self._predictor: Optional[SpectatorNetPredictor] = None
        # Per-camera sliding observation window (up to 30 frames for SpectatorNet)
        self._obs_windows: Dict[str, deque[Observation]] = {}
        self._window_lock = threading.Lock()
        self._last_predict_time: Dict[str, float] = {}

    @property
    def predictor(self) -> SpectatorNetPredictor:
        if self._predictor is None:
            self._predictor = SpectatorNetPredictor()
        return self._predictor

    def on_observation(self, observation: Observation) -> None:
        """Callback registered with AIPipeline."""
        camera_id = observation.camera_id
        # 1. Forward spatial observation to EventEngine (for zone dwell & loitering)
        self.engine.submit_observation(observation)

        # 2. Maintain rolling observation window for SpectatorNet temporal inference
        with self._window_lock:
            if camera_id not in self._obs_windows:
                self._obs_windows[camera_id] = deque(maxlen=30)
            window = self._obs_windows[camera_id]
            window.append(observation)

        now = time.time()
        last_t = self._last_predict_time.get(camera_id, 0.0)

        # Execute SpectatorNet inference at ~1-2 Hz once at least 10 frames are collected
        if len(window) >= 10 and (now - last_t >= 0.8):
            self._last_predict_time[camera_id] = now
            try:
                obs_list = list(window)
                pred = self.predictor.predict_window(obs_list, camera_id)
                self.engine.submit_prediction(pred)
            except Exception as e:
                print(f"[EventEngineService] Prediction error on camera '{camera_id}': {e}")

    def on_stream_frame(self, camera_id: str, frame, timestamp: float, frame_index: int) -> None:
        """Callback to feed decoded frames into the rolling media ring buffer."""
        self.engine.recording_mgr.ingest_frame(camera_id, frame, timestamp, frame_index)

    def start(self) -> None:
        self.engine.start()

    def stop(self) -> None:
        self.engine.stop()


event_engine_service = EventEngineService()
event_engine = event_engine_service.engine
