#!/usr/bin/env python3
"""
Smart Spectator - Model Evaluation Pipeline
Conforms to Section 21 of Phase 10 Specification.
Evaluates local ONNX model artifacts on host silicon:
- MODEL QUALITY: Precision, Recall, F1-Score, Accuracy, Confusion Matrix.
- SYSTEM PERFORMANCE: Mean Latency, P50, P95, Throughput (FPS), Model Footprint (Bytes).
Outputs structured evaluation artifact to artifacts/evaluation/.
Zero external network/cloud dependencies.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Dict, Any, List
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from ai.models.registry import model_registry


def evaluate_temporal_model(
    model_id: str = "spectatornet_v1_int8",
    num_samples: int = 50,
    output_dir: Path = Path("artifacts/evaluation"),
) -> Dict[str, Any]:
    """
    Evaluates SpectatorNet temporal model artifact.
    Separates MODEL QUALITY metrics from SYSTEM PERFORMANCE metrics.
    """
    if ort is None:
        raise RuntimeError("onnxruntime is not installed.")

    model = model_registry.get_model(model_id)
    if not model or not Path(model.file_path).exists():
        raise FileNotFoundError(f"Model artifact '{model_id}' not found.")

    model_path = Path(model.file_path)
    file_size_bytes = model_path.stat().st_size

    # 1. Setup Inference Session
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    # 2. Synthesize Deterministic Synthetic Evaluation Dataset: shape (1, 30, 166)
    from ai.datasets.constants import DEFAULT_EVENT_CLASSES
    class_names = DEFAULT_EVENT_CLASSES
    num_classes = len(class_names)
    np.random.seed(1337)
    ground_truth = np.random.randint(0, num_classes, size=num_samples).tolist()
    test_inputs = [np.random.randn(1, 30, 166).astype(np.float32) for _ in range(num_samples)]

    # 3. Warm-up
    for _ in range(5):
        session.run(None, {input_name: test_inputs[0]})

    # 4. Benchmarking Latencies & Collecting Predictions
    latencies_ms: List[float] = []
    predictions: List[int] = []

    for sample in test_inputs:
        t0 = time.perf_counter()
        out = session.run(None, {input_name: sample})[0]
        elapsed = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed)
        pred_cls = int(np.argmax(out[0]))
        predictions.append(pred_cls)

    # 5. Calculate MODEL QUALITY Metrics
    confusion_matrix = [[0] * num_classes for _ in range(num_classes)]
    for y_true, y_pred in zip(ground_truth, predictions):
        confusion_matrix[y_true][y_pred] += 1
    class_metrics = {}
    f1_list = []
    for c in range(num_classes):
        tp = confusion_matrix[c][c]
        fp = sum(confusion_matrix[i][c] for i in range(num_classes) if i != c)
        fn = sum(confusion_matrix[c][j] for j in range(num_classes) if j != c)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_list.append(f1)

        class_metrics[class_names[c]] = {
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1_score": round(f1, 3),
            "support": sum(confusion_matrix[c]),
        }

    correct_total = sum(1 for y_true, y_pred in zip(ground_truth, predictions) if y_true == y_pred)
    accuracy = round(correct_total / num_samples, 3)
    macro_f1 = round(sum(f1_list) / len(f1_list), 3)

    # 6. Calculate SYSTEM PERFORMANCE Metrics
    mean_lat = round(float(np.mean(latencies_ms)), 3)
    p50_lat = round(float(np.percentile(latencies_ms, 50)), 3)
    p95_lat = round(float(np.percentile(latencies_ms, 95)), 3)
    p99_lat = round(float(np.percentile(latencies_ms, 99)), 3)
    fps = round(1000.0 / mean_lat, 1) if mean_lat > 0 else 0.0

    report = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "model_name": model.name,
        "version": model.version,
        "precision": model.precision,
        "runtime": model.runtime,
        "test_dataset": {
            "num_samples": num_samples,
            "synthetic_samples": num_samples,
            "disclaimer": "Metrics calculated against synthetic evaluation benchmark.",
        },
        "MODEL_QUALITY": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "class_metrics": class_metrics,
            "confusion_matrix": confusion_matrix,
        },
        "SYSTEM_PERFORMANCE": {
            "file_size_bytes": file_size_bytes,
            "mean_latency_ms": mean_lat,
            "p50_latency_ms": p50_lat,
            "p95_latency_ms": p95_lat,
            "p99_latency_ms": p99_lat,
            "throughput_fps": fps,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / f"eval_{model_id}.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Evaluation report generated: {report_file}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate local model quality and system performance.")
    parser.add_argument("--model-id", default="spectatornet_v1_int8", help="Registered model ID to evaluate")
    parser.add_argument("--samples", type=int, default=50, help="Number of benchmark samples")
    args = parser.parse_args()

    evaluate_temporal_model(model_id=args.model_id, num_samples=args.samples)
