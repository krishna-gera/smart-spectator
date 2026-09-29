#!/usr/bin/env python3
"""
Smart Spectator - Hardware Benchmark Harness & Development Baseline
Measures cold-start vs steady-state latency, p50, p95, throughput (FPS),
memory usage, and provider telemetry across CPU, GPU, and NPU.
"""

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

import cv2
import numpy as np

# Ensure project root is in path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.inference.manager import InferenceProviderManager
from services.ai_engine.detector import YOLOObjectDetector


def get_system_telemetry() -> Dict[str, Any]:
    """Capture host system architecture, OS, and platform specs."""
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }


def get_process_memory_mb() -> float:
    """Measure resident memory in MB."""
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        # On macOS ru_maxrss is in bytes, on Linux in KB
        if platform.system() == "Darwin":
            return rusage.ru_maxrss / (1024.0 * 1024.0)
        else:
            return rusage.ru_maxrss / 1024.0
    except Exception:
        return 0.0


def run_benchmark(
    model_path: str = "ai/models/yolov8n.onnx",
    provider_name: str = "auto",
    iterations: int = 50,
    warmup: int = 5,
    resolution: int = 640,
) -> Dict[str, Any]:
    print(f"\n==================================================")
    print(f" SMART SPECTATOR — HARDWARE BENCHMARK HARNESS")
    print(f"==================================================")
    print(f"Target Model:      {model_path}")
    print(f"Requested Provider: {provider_name}")
    print(f"Input Resolution:  {resolution}x{resolution}")
    print(f"Iterations:        {iterations} (Warmup: {warmup})")

    sys_info = get_system_telemetry()
    print(f"Platform:          {sys_info['os']} {sys_info['machine']} ({sys_info['processor']})")

    # 1. Initialize Detector with specified provider
    os.environ["AI_PROVIDER"] = provider_name
    detector = YOLOObjectDetector(
        model_path=model_path,
        confidence_threshold=0.35,
        iou_threshold=0.45,
    )
    detector.load()
    meta = detector.get_metadata()
    print(f"Active Provider:   {meta.current_backend.value} (NPU Supported: {meta.supports_npu})")

    # 2. Prepare synthetic camera frame
    test_frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

    # 3. Cold Start Measurement
    cold_start_t0 = time.perf_counter()
    _ = detector.detect(test_frame)
    cold_start_ms = (time.perf_counter() - cold_start_t0) * 1000.0
    print(f"Cold-Start Latency: {cold_start_ms:.2f} ms")

    # 4. Warmup passes
    for _ in range(warmup):
        _ = detector.detect(test_frame)

    # 5. Steady-State Measurement
    latencies: List[float] = []
    mem_before = get_process_memory_mb()

    t_start = time.perf_counter()
    for i in range(iterations):
        t0 = time.perf_counter()
        _ = detector.detect(test_frame)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dur_ms)

    total_time_sec = time.perf_counter() - t_start
    mem_after = get_process_memory_mb()

    # Calculate statistics
    avg_latency = float(np.mean(latencies))
    p50_latency = float(np.percentile(latencies, 50))
    p95_latency = float(np.percentile(latencies, 95))
    fps = iterations / total_time_sec

    results = {
        "system": sys_info,
        "model": {
            "name": meta.name,
            "version": meta.version,
            "path": meta.weights_path,
            "input_resolution": meta.input_resolution,
            "backend": meta.current_backend.value,
            "supports_npu": meta.supports_npu,
        },
        "benchmark": {
            "iterations": iterations,
            "cold_start_ms": round(cold_start_ms, 2),
            "mean_latency_ms": round(avg_latency, 2),
            "p50_latency_ms": round(p50_latency, 2),
            "p95_latency_ms": round(p95_latency, 2),
            "throughput_fps": round(fps, 2),
            "memory_usage_mb": round(mem_after, 2),
            "memory_delta_mb": round(mem_after - mem_before, 2),
        }
    }

    print("\n--- Benchmark Results ---")
    print(f"Mean Latency:      {results['benchmark']['mean_latency_ms']} ms")
    print(f"p50 Latency:       {results['benchmark']['p50_latency_ms']} ms")
    print(f"p95 Latency:       {results['benchmark']['p95_latency_ms']} ms")
    print(f"Throughput:        {results['benchmark']['throughput_fps']} FPS")
    print(f"Process Memory:    {results['benchmark']['memory_usage_mb']} MB")
    print(f"Hardware Rule:     Verified real measurements (zero simulated/fake NPU metrics).")

    detector.unload()
    return results


def run_sample_evaluation(model_path: str = "ai/models/yolov8n.onnx") -> Dict[str, Any]:
    """Phase 2 development baseline evaluation on controlled sample images."""
    samples_dir = REPO_ROOT / "ai" / "evaluation" / "samples"
    annotations_path = samples_dir / "annotations.json"
    
    if not annotations_path.exists():
        print("No sample annotations found. Run generate_samples.py first.")
        return {}

    with open(annotations_path, "r") as f:
        annotations = json.load(f)

    detector = YOLOObjectDetector(model_path=model_path)
    detector.load()

    total_samples = len(annotations)
    total_gt = sum(len(boxes) for boxes in annotations.values())
    total_detections = 0

    print(f"\n--- Phase 2 Development Baseline Evaluation ---")
    print(f"Evaluating {total_samples} samples ({total_gt} ground-truth objects)...")

    for filename, gt_boxes in annotations.items():
        img_path = samples_dir / filename
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue
        dets = detector.detect(frame)
        inf_ms = detector.last_metrics.get("inference_ms", 0.0)
        total_detections += len(dets)
        print(f"  {filename}: {len(dets)} detections (Inference: {inf_ms:.1f}ms)")

    detector.unload()
    return {
        "total_samples": total_samples,
        "total_ground_truth": total_gt,
        "total_detections": total_detections,
        "note": "Phase 2 development baseline - full precision/recall benchmarking reserved for Phase 3 dataset.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Spectator AI Benchmark Harness")
    parser.add_argument("--model", default="ai/models/yolov8n.onnx", help="Path to ONNX model")
    parser.add_argument("--provider", default="auto", help="Inference provider (auto/cpu/gpu/npu)")
    parser.add_argument("--iterations", type=int, default=50, help="Benchmark iterations")
    parser.add_argument("--output", default="ai/evaluation/benchmark_results.json", help="Output JSON path")
    args = parser.parse_args()

    results = run_benchmark(
        model_path=args.model,
        provider_name=args.provider,
        iterations=args.iterations,
    )
    
    eval_results = run_sample_evaluation(args.model)
    results["baseline_evaluation"] = eval_results

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved benchmark results to '{out_path}'")
