#!/usr/bin/env python3
"""
Smart Spectator - Snapdragon Runtime & Hardware Validator
Conforms to Section 3 of Phase 8 Master Specification.
Checks platform OS, architecture, Snapdragon/ARM64 features, ONNX Runtime,
QNN/DirectML/CPU execution providers, and model compatibility.
Never fabricates performance metrics.
"""

import sys
import os
import json
import time
import platform
import psutil
from pathlib import Path
from typing import Dict, Any, List

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

try:
    import numpy as np
except ImportError:
    np = None


def inspect_environment() -> Dict[str, Any]:
    os_name = platform.system()
    os_version = platform.version()
    os_release = platform.release()
    arch = platform.machine()
    proc = platform.processor() or "unknown"
    mem_total_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    cpu_cores = psutil.cpu_count(logical=True)

    is_windows = "windows" in os_name.lower()
    is_arm64 = "arm" in arch.lower() or "aarch64" in arch.lower()

    ort_version = ort.__version__ if HAS_ORT else "not_installed"
    available_providers = ort.get_available_providers() if HAS_ORT else []

    qnn_available = "QNNExecutionProvider" in available_providers
    dml_available = "DmlExecutionProvider" in available_providers
    coreml_available = "CoreMLExecutionProvider" in available_providers
    cpu_available = "CPUExecutionProvider" in available_providers

    # Qualcomm runtime library detection (Windows on Snapdragon)
    qnn_libs_found = []
    if is_windows:
        candidates = [
            Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "QnnHtp.dll",
            Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "QnnHtpV73Stub.dll",
            Path(os.environ.get("SystemRoot", "C:\\Windows")) / "System32" / "QnnSystem.dll",
        ]
        for c in candidates:
            if c.exists():
                qnn_libs_found.append(c.name)

    return {
        "os": os_name,
        "os_version": os_version,
        "os_release": os_release,
        "architecture": arch,
        "processor": proc,
        "memory_total_gb": mem_total_gb,
        "cpu_cores": cpu_cores,
        "is_windows_arm64": is_windows and is_arm64,
        "onnxruntime_version": ort_version,
        "available_providers": available_providers,
        "qnn_available": qnn_available,
        "directml_available": dml_available,
        "coreml_available": coreml_available,
        "cpu_available": cpu_available,
        "qualcomm_libraries_found": qnn_libs_found,
    }


def benchmark_model_on_provider(model_path: str, input_feed_builder, provider_name: str, iterations: int = 50) -> Dict[str, Any]:
    """Runs genuine benchmark on the specified provider; never fabricates."""
    if not HAS_ORT or not Path(model_path).exists():
        return {"status": "NOT_AVAILABLE", "error": f"Model {model_path} not found or ORT absent"}

    t_init_start = time.perf_counter()
    sess_opts = ort.SessionOptions()
    sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    try:
        session = ort.InferenceSession(model_path, sess_opts, providers=[provider_name])
    except Exception as e:
        return {"status": "FAILED", "provider": provider_name, "error": str(e)}
    init_time_ms = round((time.perf_counter() - t_init_start) * 1000.0, 2)

    actual_provider = session.get_providers()[0]
    input_feed = input_feed_builder()

    # Warm-up pass
    t_warm_start = time.perf_counter()
    session.run(None, input_feed)
    warmup_ms = round((time.perf_counter() - t_warm_start) * 1000.0, 2)

    # Benchmark loop
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        session.run(None, input_feed)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    mean = float(np.mean(latencies))
    fps = round(1000.0 / mean, 1) if mean > 0 else 0.0

    return {
        "status": "MEASURED",
        "requested_provider": provider_name,
        "active_provider": actual_provider,
        "init_time_ms": init_time_ms,
        "warmup_ms": warmup_ms,
        "iterations": iterations,
        "mean_ms": round(mean, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "throughput_fps": fps,
    }


def main():
    print("=" * 60)
    print(" Smart Spectator — Snapdragon Runtime & Hardware Validation")
    print("=" * 60)

    env = inspect_environment()
    print(f"OS: {env['os']} ({env['architecture']}) | Processor: {env['processor']}")
    print(f"RAM: {env['memory_total_gb']} GB | Logical Cores: {env['cpu_cores']}")
    print(f"ONNX Runtime: {env['onnxruntime_version']}")
    print(f"Available Providers: {env['available_providers']}")

    if env["qnn_available"]:
        print("\n[+] Qualcomm QNN Execution Provider: AVAILABLE")
        selected_provider = "QNNExecutionProvider"
    elif env["directml_available"]:
        print("\n[-] Qualcomm QNN EP not present. DirectML (GPU) AVAILABLE.")
        selected_provider = "DmlExecutionProvider"
    elif env["coreml_available"]:
        print("\n[-] Qualcomm QNN EP not present (Host is macOS). CoreML AVAILABLE.")
        selected_provider = "CoreMLExecutionProvider"
    else:
        print("\n[-] Accelerators not present. Using CPU Universal Fallback.")
        selected_provider = "CPUExecutionProvider"

    print(f"Selected Provider for Validation: {selected_provider}\n")

    # Models to test
    models_to_test = [
        {
            "name": "spectatornet_fp32",
            "path": "ai/models/releases/spectatornet_v1.onnx",
            "feed": lambda: {"temporal_features": np.random.randn(1, 30, 166).astype(np.float32)},
        },
        {
            "name": "spectatornet_int8",
            "path": "ai/models/releases/spectatornet_v1_int8.onnx",
            "feed": lambda: {"temporal_features": np.random.randn(1, 30, 166).astype(np.float32)},
        },
        {
            "name": "yolov8n_detector",
            "path": "ai/models/releases/detector_v1.onnx",
            "feed": lambda: {"images": np.random.randn(1, 3, 640, 640).astype(np.float32)},
        },
    ]

    bench_results = {}
    for m in models_to_test:
        print(f"Testing {m['name']} on {selected_provider}...")
        res = benchmark_model_on_provider(m["path"], m["feed"], selected_provider, iterations=30)
        bench_results[m["name"]] = res
        if res.get("status") == "MEASURED":
            print(f"  -> p50: {res['p50_ms']} ms | p95: {res['p95_ms']} ms | Throughput: {res['throughput_fps']} FPS")
        else:
            print(f"  -> Status: {res.get('status')} ({res.get('error')})")

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": env,
        "selected_provider": selected_provider,
        "results": bench_results,
    }

    out_dir = Path("artifacts/phase8")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "hardware_validation_report.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[OK] Validation report written to: {report_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
