#!/usr/bin/env python3
"""
Smart Spectator - Live Video Pipeline Diagnostics Harness
Conforms to Section 8 of Phase 8 Master Specification.
Measures real frame-by-frame latency and throughput through each decoupled stage:
Ingest -> Decode -> Sampler/MotionGate -> YOLO -> ByteTrack -> Observation -> SpectatorNet -> EventEngine.
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

# Ensure repository root is on sys.path
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from services.ai_engine.detector import YOLOObjectDetector
from services.ai_engine.tracker import ByteTrackTracker
from services.ai_engine.frame_sampler import AdaptiveFrameSampler
from services.ai_engine.observation_builder import ObservationBuilder
from ai.models.predictor import SpectatorNetPredictor
from services.event_engine.engine import EventEngine
from shared.schemas.v1.models import Observation


def run_pipeline_benchmark(duration_seconds: float = 5.0, target_input_fps: float = 30.0) -> Dict[str, Any]:
    print("=" * 65)
    print(" Smart Spectator — Live Video Pipeline End-to-End Diagnostics")
    print("=" * 65)
    print(f"Target Input Rate: {target_input_fps} FPS | Test Duration: {duration_seconds}s")

    # Initialize pipeline stages
    sampler = AdaptiveFrameSampler(target_fps=5.0, motion_gate_enabled=True)
    detector = YOLOObjectDetector()
    tracker = ByteTrackTracker()
    predictor = SpectatorNetPredictor(
        model_path="ai/models/releases/spectatornet_v1_int8.onnx",
        normalization_path="ai/datasets/smart_spectator/statistics/normalization.json"
    )
    event_engine = EventEngine()
    event_engine.start()

    camera_id = "cam_diag_01"
    total_frames = int(duration_seconds * target_input_fps)
    frame_interval = 1.0 / target_input_fps

    # Metrics accumulators
    ingest_latencies = []
    sampling_latencies = []
    detect_latencies = []
    track_latencies = []
    spectatornet_latencies = []
    event_latencies = []
    total_pipeline_latencies = []

    sampled_frames_count = 0
    gated_frames_count = 0
    events_triggered_count = 0

    obs_window: List[Observation] = []

    print("\nExecuting live synthetic 720p stream through pipeline...")
    start_time = time.perf_counter()

    for idx in range(total_frames):
        t_frame_start = time.perf_counter()

        # 1. Simulate 720p frame arrival (1280x720 RGB)
        t_ingest_start = time.perf_counter()
        # Alternate between static frame and dynamic frame
        if idx % 10 < 3:
            # Motion frame: Add simulated object patch
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame[200:400, 300:500] = 200
        else:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        ingest_latencies.append((time.perf_counter() - t_ingest_start) * 1000.0)

        # 2. Sampler & Motion Gating
        t_sample_start = time.perf_counter()
        now = time.time()
        should_sample, motion_detected = sampler.should_sample(frame, now)
        sampling_latencies.append((time.perf_counter() - t_sample_start) * 1000.0)

        if not should_sample:
            gated_frames_count += 1
            # Maintain nominal frame pacing
            elapsed_frame = time.perf_counter() - t_frame_start
            sleep_time = frame_interval - elapsed_frame
            if sleep_time > 0:
                time.sleep(sleep_time)
            continue

        sampled_frames_count += 1

        # 3. Detection
        t_det_start = time.perf_counter()
        detections = detector.detect(frame)
        detect_latencies.append((time.perf_counter() - t_det_start) * 1000.0)

        # 4. Tracking
        t_trk_start = time.perf_counter()
        tracked = tracker.update(camera_id, detections, now)
        track_latencies.append((time.perf_counter() - t_trk_start) * 1000.0)

        # 5. Observation Build
        obs = ObservationBuilder.build(
            camera_id=camera_id,
            frame_index=idx,
            detections=detections,
            tracked_objects=tracked,
            inference_telemetry={"fps": 30.0}
        )
        obs_window.append(obs)
        if len(obs_window) > 30:
            obs_window.pop(0)

        # 6. SpectatorNet Temporal Inference (every 5 sampled frames)
        if len(obs_window) >= 10 and (sampled_frames_count % 5 == 0):
            t_sn_start = time.perf_counter()
            pred = predictor.predict_window(obs_window, camera_id)
            spectatornet_latencies.append((time.perf_counter() - t_sn_start) * 1000.0)

            # 7. Event Engine Evaluation
            t_ee_start = time.perf_counter()
            event_engine.submit_prediction(pred)
            event_latencies.append((time.perf_counter() - t_ee_start) * 1000.0)

        # Total pipeline latency for this processed frame
        total_lat = (time.perf_counter() - t_frame_start) * 1000.0
        total_pipeline_latencies.append(total_lat)

        # Pacing
        elapsed_frame = time.perf_counter() - t_frame_start
        sleep_time = frame_interval - elapsed_frame
        if sleep_time > 0:
            time.sleep(sleep_time)

    total_test_duration = time.perf_counter() - start_time
    event_engine.stop()

    def stats(arr: List[float]) -> Dict[str, float]:
        if not arr:
            return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
        a = np.array(arr)
        return {
            "mean": round(float(np.mean(a)), 2),
            "p50": round(float(np.percentile(a, 50)), 2),
            "p95": round(float(np.percentile(a, 95)), 2),
            "max": round(float(np.max(a)), 2),
        }

    report = {
        "test_metadata": {
            "duration_seconds": round(total_test_duration, 2),
            "total_frames_ingested": total_frames,
            "sampled_frames": sampled_frames_count,
            "gated_frames": gated_frames_count,
            "effective_ingest_fps": round(total_frames / total_test_duration, 1),
            "motion_gating_bypass_ratio": round(gated_frames_count / total_frames if total_frames else 0.0, 3),
        },
        "stage_latencies_ms": {
            "ingest_and_buffer": stats(ingest_latencies),
            "frame_sampler_motion_gate": stats(sampling_latencies),
            "yolov8n_detection": stats(detect_latencies),
            "bytetrack_tracking": stats(track_latencies),
            "spectatornet_temporal_gru": stats(spectatornet_latencies),
            "event_engine_evaluation": stats(event_latencies),
            "end_to_end_processed_frame": stats(total_pipeline_latencies),
        },
    }

    print("\n--- Diagnostic Summary ---")
    print(f"Total Ingested Frames: {total_frames} @ {report['test_metadata']['effective_ingest_fps']} FPS")
    print(f"Sampled Frames: {sampled_frames_count} | Gated Frames: {gated_frames_count} ({report['test_metadata']['motion_gating_bypass_ratio'] * 100:.1f}% reduction)")
    print(f"Detection Latency (p50):    {report['stage_latencies_ms']['yolov8n_detection']['p50']} ms")
    print(f"Tracking Latency (p50):     {report['stage_latencies_ms']['bytetrack_tracking']['p50']} ms")
    print(f"SpectatorNet Latency (p50): {report['stage_latencies_ms']['spectatornet_temporal_gru']['p50']} ms")
    print(f"End-to-End Latency (p50):   {report['stage_latencies_ms']['end_to_end_processed_frame']['p50']} ms")

    out_dir = Path("artifacts/phase8")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "pipeline_diagnostics.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[OK] Pipeline diagnostic report written to: {report_file}")
    print("=" * 65)

    return report


if __name__ == "__main__":
    run_pipeline_benchmark(duration_seconds=3.0, target_input_fps=30.0)
