"""
Smart Spectator - Asynchronous AI Perception Pipeline
Implements Section 18 & 19: Non-blocking worker queue, bounded frame drops,
multi-camera tracker isolation, and observation broadcasting.
"""

import time
import asyncio
import threading
from queue import Queue, Full, Empty
from typing import Dict, Optional, Tuple, Callable, List, Any
import numpy as np

from shared.schemas.v1.models import Observation, Detection, TrackedObject
from .detector import YOLOObjectDetector
from .tracker import ByteTrackTracker
from .frame_sampler import AdaptiveFrameSampler
from .observation_builder import ObservationBuilder


class CameraPerceptionContext:
    """Isolates frame sampler, tracker, and queues per camera stream."""

    def __init__(self, camera_id: str, target_fps: float = 5.0, motion_gate: bool = True):
        self.camera_id = camera_id
        self.sampler = AdaptiveFrameSampler(target_fps=target_fps, motion_gate_enabled=motion_gate)
        self.tracker = ByteTrackTracker()
        self.queue: Queue = Queue(maxsize=2) # Bounded queue strictly preventing bufferbloat
        self.latest_observation: Optional[Observation] = None
        
        # Telemetry
        self.frames_received = 0
        self.frames_sampled = 0
        self.frames_dropped = 0
        self.last_inference_time_ms: float = 0.0
        self.rolling_inference_fps: float = 0.0
        self._fps_time = time.time()
        self._fps_count = 0


class AIPipeline:
    """
    Central AI Perception Pipeline Orchestrator.
    Consumes decoded frames from the stream engine and yields structured Observations.
    """

    def __init__(self, detector: Optional[YOLOObjectDetector] = None):
        self.detector = detector or YOLOObjectDetector()
        self.contexts: Dict[str, CameraPerceptionContext] = {}
        self.is_running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._observation_callbacks: List[Callable[[Observation], None]] = []

    def get_or_create_context(self, camera_id: str) -> CameraPerceptionContext:
        if camera_id not in self.contexts:
            self.contexts[camera_id] = CameraPerceptionContext(camera_id)
        return self.contexts[camera_id]

    def remove_context(self, camera_id: str):
        if camera_id in self.contexts:
            del self.contexts[camera_id]

    def register_callback(self, callback: Callable[[Observation], None]):
        """Registers a listener for newly emitted Observations (e.g. Event Engine or UI)."""
        self._observation_callbacks.append(callback)

    def submit_frame(self, camera_id: str, frame: np.ndarray, frame_index: int, timestamp: Optional[float] = None) -> bool:
        """
        Non-blocking ingestion entrypoint called by stream engine.
        Applies frame decimation and drops stale frames if worker queue is full.
        """
        ctx = self.get_or_create_context(camera_id)
        ctx.frames_received += 1
        now = timestamp or time.time()

        should_process, _ = ctx.sampler.should_sample(frame, now)
        if not should_process:
            return False

        ctx.frames_sampled += 1
        item = (camera_id, frame.copy(), frame_index, now)

        # Bounded non-blocking queue handling: Drop stale frame if queue is full
        try:
            ctx.queue.put_nowait(item)
            return True
        except Full:
            ctx.frames_dropped += 1
            # Evict oldest frame to prioritize the newest frame
            try:
                ctx.queue.get_nowait()
                ctx.queue.put_nowait(item)
                return True
            except Exception:
                return False

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        print("[AIPipeline] AI Perception Pipeline background worker started.")

    def stop(self):
        self.is_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)
        print("[AIPipeline] AI Perception Pipeline worker stopped.")

    def _worker_loop(self):
        while self.is_running:
            processed_any = False
            for camera_id, ctx in list(self.contexts.items()):
                try:
                    camera_id, frame, frame_index, ts = ctx.queue.get_nowait()
                    processed_any = True
                    
                    t0 = time.perf_counter()
                    # 1. Level 1: Object Detection
                    detections = self.detector.detect(frame)
                    t_detect = (time.perf_counter() - t0) * 1000.0

                    # 2. Level 2: Multi-Object Tracking
                    t1 = time.perf_counter()
                    tracked_objects = ctx.tracker.update(camera_id, detections, ts)
                    t_track = (time.perf_counter() - t1) * 1000.0

                    t_total = (time.perf_counter() - t0) * 1000.0
                    ctx.last_inference_time_ms = round(t_total, 2)

                    # Update rolling inference FPS
                    ctx._fps_count += 1
                    elapsed = time.time() - ctx._fps_time
                    if elapsed >= 1.0:
                        ctx.rolling_inference_fps = round(ctx._fps_count / elapsed, 1)
                        ctx._fps_count = 0
                        ctx._fps_time = time.time()

                    # 3. Build Observation
                    telemetry = {
                        "detector_model": self.detector.model_id,
                        "backend": self.detector.backend.value,
                        "detection_ms": round(t_detect, 2),
                        "tracking_ms": round(t_track, 2),
                        "total_ai_latency_ms": round(t_total, 2),
                        "inference_fps": ctx.rolling_inference_fps
                    }
                    obs = ObservationBuilder.build(camera_id, frame_index, detections, tracked_objects, telemetry)
                    ctx.latest_observation = obs

                    # Dispatch to listeners
                    for cb in self._observation_callbacks:
                        try:
                            cb(obs)
                        except Exception as e:
                            print(f"[AIPipeline] Observation callback error: {e}")

                except Empty:
                    continue
                except Exception as e:
                    print(f"[AIPipeline] Inference loop error for '{camera_id}': {e}")

            if not processed_any:
                time.sleep(0.005) # Prevent CPU spinning when queues are empty

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns aggregated AI engine metrics across all cameras."""
        camera_stats = {}
        for cam_id, ctx in self.contexts.items():
            camera_stats[cam_id] = {
                "frames_received": ctx.frames_received,
                "frames_sampled": ctx.frames_sampled,
                "frames_dropped": ctx.frames_dropped,
                "latency_ms": ctx.last_inference_time_ms,
                "inference_fps": ctx.rolling_inference_fps,
                "active_tracks_count": len([t for t in (ctx.latest_observation.tracked_objects if ctx.latest_observation else []) if t.is_active])
            }

        return {
            "active_model": self.detector.model_id,
            "active_backend": self.detector.backend.value,
            "is_model_loaded": self.detector.is_loaded,
            "camera_contexts": camera_stats,
            "performance": self.detector.get_performance()
        }


ai_pipeline = AIPipeline()
