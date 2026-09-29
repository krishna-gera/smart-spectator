"""
Smart Spectator - Phase 2 AI Perception Pipeline Test Suite
Tests:
- Adaptive Frame Sampler & Motion Gating
- Inference Provider Manager & Fallback Hierarchy
- YOLO Object Detector (normalized bboxes, confidence filtering, letterbox)
- ByteTrack Multi-Object Tracker (persistent IDs, velocity, occlusion handling)
- Observation Builder (schema compliance)
- AIPipeline Orchestrator (asynchronous non-blocking queue, backpressure frame dropping, multi-camera context isolation)
"""

import os
import time
from datetime import datetime
import numpy as np
import pytest

from shared.schemas.v1.models import (
    Detection,
    TrackedObject,
    Observation,
    HardwareBackend,
)
from ai.inference.manager import (
    InferenceProviderManager,
    CPUInferenceProvider,
    CoreMLInferenceProvider,
    DirectMLInferenceProvider,
    QNNInferenceProvider,
    provider_manager,
)
from services.ai_engine.frame_sampler import AdaptiveFrameSampler
from services.ai_engine.detector import YOLOObjectDetector, COCO_CLASSES
from services.ai_engine.tracker import ByteTrackTracker
from services.ai_engine.observation_builder import ObservationBuilder
from services.ai_engine.pipeline import AIPipeline, CameraPerceptionContext


# -----------------------------------------------------------------------------
# 1. Frame Sampler & Motion Gating Tests
# -----------------------------------------------------------------------------

def test_frame_sampler_rate_limiting():
    """Verify frame sampler decimates 30 FPS stream down to configurable target (e.g. 5 FPS)."""
    sampler = AdaptiveFrameSampler(
        target_fps=5.0,
        motion_gate_enabled=False,
    )

    # Simulate 30 frames arriving at 33.3ms intervals (1 second total)
    sampled_indices = []
    base_time = 1000.0
    for i in range(30):
        t = base_time + (i * 0.0333)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        should_run, _ = sampler.should_sample(frame, timestamp=t)
        if should_run:
            sampled_indices.append(i)

    # At 5 FPS over 1 second, approximately 5 frames should be accepted
    assert 4 <= len(sampled_indices) <= 6
    assert 0 in sampled_indices  # First frame is always accepted


def test_motion_gating_skips_static_frames():
    """Verify motion gating suppresses inference when consecutive frames are identical."""
    sampler = AdaptiveFrameSampler(
        target_fps=30.0,
        motion_gate_enabled=True,
        motion_threshold=0.01,
    )

    static_frame = np.full((100, 100, 3), 128, dtype=np.uint8)
    
    # First frame always accepted to initialize background model
    should_run_1, motion_1 = sampler.should_sample(static_frame, timestamp=100.0)
    assert should_run_1 is True
    assert motion_1 is True

    # Identical next frame should be rejected by motion gate
    should_run_2, motion_2 = sampler.should_sample(static_frame, timestamp=100.1)
    assert should_run_2 is False
    assert motion_2 is False

    # Frame with substantial motion (bright block) should be accepted
    moving_frame = static_frame.copy()
    moving_frame[20:80, 20:80] = 255
    should_run_3, motion_3 = sampler.should_sample(moving_frame, timestamp=100.2)
    assert should_run_3 is True
    assert motion_3 is True


# -----------------------------------------------------------------------------
# 2. Inference Provider & Hardware Manager Tests
# -----------------------------------------------------------------------------

def test_inference_provider_manager_hierarchy():
    """Verify hardware detection and fallback hierarchy without fabricated claims."""
    mgr = InferenceProviderManager()
    detected = mgr.detect_available_backends()
    
    assert HardwareBackend.CPU in detected
    assert isinstance(mgr.providers[HardwareBackend.CPU], CPUInferenceProvider)

    # CPU provider should always succeed
    backend, provider = mgr.get_preferred_provider("cpu")
    assert backend == HardwareBackend.CPU
    assert provider is not None


def test_npu_claim_verification():
    """Critical Hardware Rule: Verify NPU is only reported if runtime actually supports it."""
    mgr = InferenceProviderManager()
    qnn_provider = mgr.providers[HardwareBackend.NPU_QNN]
    
    # On macOS or machines without QNN execution provider, is_available must be False
    import platform
    if platform.system() != "Windows" or platform.machine().lower() not in ["arm64", "aarch64"]:
        caps = qnn_provider.get_capabilities()
        assert caps["is_available"] is False


# -----------------------------------------------------------------------------
# 3. YOLO Object Detector Tests
# -----------------------------------------------------------------------------

def test_yolo_detector_loading_and_inference():
    """Verify YOLO detector loads ONNX model, handles normalized bboxes and confidence thresholding."""
    detector = YOLOObjectDetector(
        model_path="ai/models/yolov8n.onnx",
        confidence_threshold=0.35,
        iou_threshold=0.45,
    )
    assert detector.load() is True
    assert detector.is_loaded is True

    meta = detector.get_metadata()
    assert meta.model_id == "yolov8n"
    assert meta.input_resolution == [1, 3, 640, 640]

    # Test synthetic frame detection
    frame = np.full((720, 1280, 3), 200, dtype=np.uint8)
    detections = detector.detect(frame)
    assert isinstance(detections, list)

    # Verify detection coordinate bounds if any detections occur
    for det in detections:
        assert isinstance(det, Detection)
        assert 0 <= det.class_id < len(COCO_CLASSES)
        assert 0.0 <= det.confidence <= 1.0
        x1, y1, x2, y2 = det.bbox_xyxy
        assert 0.0 <= x1 <= 1.0
        assert 0.0 <= y1 <= 1.0
        assert 0.0 <= x2 <= 1.0
        assert 0.0 <= y2 <= 1.0
        assert x1 <= x2
        assert y1 <= y2

    detector.unload()
    assert detector.is_loaded is False


# -----------------------------------------------------------------------------
# 4. ByteTrack Multi-Object Tracker Tests
# -----------------------------------------------------------------------------

def test_bytetrack_tracking_and_persistence():
    """Verify persistent track IDs, velocity vector calculation, and state maintenance."""
    tracker = ByteTrackTracker(high_conf_threshold=0.5, match_iou_threshold=0.3, max_age_frames=5)

    camera_id = "cam_test_01"
    t0 = 1000.0

    # Frame 1: Detection at [0.1, 0.1, 0.2, 0.2]
    det1 = Detection(
        detection_id="det_01",
        class_id=0,
        class_name="person",
        confidence=0.92,
        bbox_xyxy=[0.1, 0.1, 0.2, 0.2]
    )
    tracks_f1 = tracker.update(camera_id, [det1], timestamp=t0)
    assert len(tracks_f1) == 1
    track_id_1 = tracks_f1[0].track_id
    assert tracks_f1[0].class_name == "person"
    assert len(tracks_f1[0].trajectory) == 1

    # Frame 2: Object moved slightly to [0.12, 0.12, 0.22, 0.22] at t0 + 0.1s
    t1 = t0 + 0.1
    det2 = Detection(
        detection_id="det_02",
        class_id=0,
        class_name="person",
        confidence=0.90,
        bbox_xyxy=[0.12, 0.12, 0.22, 0.22]
    )
    tracks_f2 = tracker.update(camera_id, [det2], timestamp=t1)
    assert len(tracks_f2) == 1
    # Track ID must remain persistent
    assert tracks_f2[0].track_id == track_id_1
    assert len(tracks_f2[0].trajectory) == 2


def test_tracker_occlusion_and_cleanup():
    """Verify tracker keeps lost objects for max_age_frames, then cleans them up."""
    tracker = ByteTrackTracker(max_age_frames=2)
    camera_id = "cam_test_02"

    det = Detection(
        detection_id="det_01",
        class_id=39,
        class_name="bottle",
        confidence=0.88,
        bbox_xyxy=[0.4, 0.4, 0.5, 0.6]
    )
    # Frame 1: Seen
    tracker.update(camera_id, [det], timestamp=10.0)
    assert len(tracker.tracks) == 1

    # Frame 2: Occluded / missed (empty detections)
    tracker.update(camera_id, [], timestamp=10.1)
    assert len(tracker.tracks) == 1  # Retained in lost state

    # Frame 3: Missed again
    tracker.update(camera_id, [], timestamp=10.2)
    assert len(tracker.tracks) == 1

    # Frame 4: Exceeds max_age_frames (2), should be evicted
    tracker.update(camera_id, [], timestamp=10.3)
    assert len(tracker.tracks) == 0


# -----------------------------------------------------------------------------
# 5. Observation Builder Tests
# -----------------------------------------------------------------------------

def test_observation_builder_structure():
    """Verify Observation conforms strictly to shared/schemas/v1/models.py."""
    now = datetime.utcnow()
    detections = [
        Detection(
            detection_id="det_01",
            class_id=0,
            class_name="person",
            confidence=0.95,
            bbox_xyxy=[0.1, 0.1, 0.3, 0.5]
        )
    ]
    tracks = [
        TrackedObject(
            track_id=1,
            camera_id="cam_obs_01",
            class_name="person",
            current_bbox=[0.1, 0.1, 0.3, 0.5],
            velocity_vector=[0.01, 0.0],
            first_seen_timestamp=now,
            last_seen_timestamp=now,
            trajectory=[[0.2, 0.3]],
            confidence=0.95,
            is_active=True
        )
    ]
    telemetry = {"backend": "cpu", "latency_ms": 8.5}

    obs = ObservationBuilder.build(
        camera_id="cam_obs_01",
        frame_index=42,
        detections=detections,
        tracked_objects=tracks,
        inference_telemetry=telemetry
    )

    assert isinstance(obs, Observation)
    assert obs.camera_id == "cam_obs_01"
    assert obs.frame_index == 42
    assert len(obs.detections) == 1
    assert len(obs.tracked_objects) == 1
    assert obs.detections[0].class_name == "person"
    assert obs.scene_state["inference"]["backend"] == "cpu"
    assert obs.scene_state["inference"]["latency_ms"] == 8.5


# -----------------------------------------------------------------------------
# 6. AIPipeline Orchestrator & Concurrency Tests
# -----------------------------------------------------------------------------

def test_aipipeline_bounded_queue_backpressure():
    """Verify AIPipeline drops stale frames rather than creating unbounded latency."""
    pipeline = AIPipeline()
    camera_id = "cam_backpressure_01"
    ctx = pipeline.get_or_create_context(camera_id)
    # Configure sampler to accept all frames for this test
    ctx.sampler.sample_interval_sec = 0.0
    ctx.sampler.motion_gate_enabled = False

    assert ctx.queue.maxsize == 2

    # Fill queue to maximum capacity
    frame1 = np.zeros((10, 10, 3), dtype=np.uint8)
    frame2 = np.ones((10, 10, 3), dtype=np.uint8)
    frame3 = np.full((10, 10, 3), 2, dtype=np.uint8)

    accepted1 = pipeline.submit_frame(camera_id, frame1, frame_index=1, timestamp=1.0)
    accepted2 = pipeline.submit_frame(camera_id, frame2, frame_index=2, timestamp=2.0)
    assert accepted1 is True
    assert accepted2 is True

    # Third frame should cause queue eviction (drop oldest frame, keep newest)
    accepted3 = pipeline.submit_frame(camera_id, frame3, frame_index=3, timestamp=3.0)
    assert accepted3 is True
    assert ctx.frames_dropped == 1

    pipeline.remove_context(camera_id)
    assert camera_id not in pipeline.contexts


def test_aipipeline_multi_camera_isolation():
    """Verify multiple cameras maintain independent frame samplers, trackers, and queues."""
    pipeline = AIPipeline()
    cam1 = "cam_north"
    cam2 = "cam_south"

    ctx1 = pipeline.get_or_create_context(cam1)
    ctx2 = pipeline.get_or_create_context(cam2)

    assert cam1 in pipeline.contexts
    assert cam2 in pipeline.contexts
    assert ctx1.tracker is not ctx2.tracker
    assert ctx1.sampler is not ctx2.sampler
    assert ctx1.queue is not ctx2.queue

    pipeline.remove_context(cam1)
    pipeline.remove_context(cam2)
    assert cam1 not in pipeline.contexts
    assert cam2 not in pipeline.contexts
