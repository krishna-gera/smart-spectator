"""
Smart Spectator - Adaptive Frame Sampler & Motion Gating
Implements Section 8 & Section 18: Decimates 30 FPS video to 5 FPS inference rate,
bypasses static scenes via low-cost pixel variance to preserve NPU/CPU compute.
"""

import time
from typing import Tuple, Optional, Dict, Any
import numpy as np
import cv2


class AdaptiveFrameSampler:
    """
    Samples incoming high-frame-rate video streams at a decimated inference frequency
    and performs fast motion pre-filtering before invoking deep neural networks.
    """

    def __init__(
        self,
        target_fps: float = 5.0,
        motion_gate_enabled: bool = True,
        motion_threshold: float = 0.005,  # 0.5% pixel change
        pixel_diff_threshold: int = 25    # Grayscale difference to count as moved
    ):
        self.target_fps = target_fps
        self.sample_interval_sec = 1.0 / target_fps if target_fps > 0 else 0.2
        self.motion_gate_enabled = motion_gate_enabled
        self.motion_threshold = motion_threshold
        self.pixel_diff_threshold = pixel_diff_threshold

        self.last_sample_time: float = 0.0
        self.prev_small_gray: Optional[np.ndarray] = None
        
        # Telemetry
        self.total_frames = 0
        self.sampled_frames = 0
        self.motion_skipped_frames = 0

    def check_motion(self, frame: np.ndarray) -> bool:
        """
        Fast low-cost motion detection:
        Downsamples to 160x90 grayscale and computes fractional pixel delta.
        """
        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        if self.prev_small_gray is None:
            self.prev_small_gray = gray
            return True # First frame always treated as active

        diff = cv2.absdiff(self.prev_small_gray, gray)
        changed_pixels = np.count_nonzero(diff > self.pixel_diff_threshold)
        total_pixels = gray.size
        motion_ratio = changed_pixels / total_pixels

        self.prev_small_gray = gray
        return bool(motion_ratio >= self.motion_threshold)

    def should_sample(self, frame: np.ndarray, timestamp: Optional[float] = None) -> Tuple[bool, bool]:
        """
        Evaluates whether the frame should enter the AI perception pipeline.
        Returns:
            Tuple (should_process_ai, has_motion)
        """
        now = timestamp if timestamp is not None else time.time()
        self.total_frames += 1

        # 1. Rate Limiting / Decimation check
        if (now - self.last_sample_time) < self.sample_interval_sec:
            return False, False

        # 2. Motion Gating check
        has_motion = True
        if self.motion_gate_enabled:
            has_motion = self.check_motion(frame)
            if not has_motion:
                self.motion_skipped_frames += 1
                self.last_sample_time = now
                return False, False

        self.last_sample_time = now
        self.sampled_frames += 1
        return True, has_motion

    def get_metrics(self) -> Dict[str, Any]:
        """Returns frame decimation and motion gating effectiveness."""
        reduction_pct = 0.0
        if self.total_frames > 0:
            reduction_pct = round((1.0 - (self.sampled_frames / self.total_frames)) * 100.0, 1)

        return {
            "target_fps": self.target_fps,
            "motion_gate_enabled": self.motion_gate_enabled,
            "total_frames_received": self.total_frames,
            "sampled_for_ai": self.sampled_frames,
            "motion_skipped": self.motion_skipped_frames,
            "compute_load_reduction_percent": reduction_pct
        }

    def reset(self):
        self.prev_small_gray = None
        self.last_sample_time = 0.0
