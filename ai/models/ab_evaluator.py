"""
Smart Spectator - Model A/B Validation Framework
Conforms to Section 17 of Phase 9 Master Specification.
Compares candidate models on real hardware: latency, memory footprint,
prediction agreement, and event classification stability.
Does NOT automatically replace production models without explicit operator action.
"""

from pathlib import Path
import time
from typing import Dict, Any, List, Optional
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from ai.models.registry import model_registry


class ModelABEvaluator:
    """
    Evaluates side-by-side performance of two registered models on local hardware.
    Operates strictly offline without external network dependencies.
    """

    def __init__(self):
        pass

    def evaluate_temporal_models(
        self,
        model_a_id: str = "spectatornet_v1_fp32",
        model_b_id: str = "spectatornet_v1_int8",
        iterations: int = 50,
    ) -> Dict[str, Any]:
        """
        Benchmarks and compares two temporal models (e.g. FP32 vs INT8).
        Measures real latency distributions, prediction distribution agreement, and artifact sizes.
        """
        if ort is None:
            raise RuntimeError("onnxruntime is not installed in the environment.")

        model_a = model_registry.get_model(model_a_id)
        model_b = model_registry.get_model(model_b_id)

        if not model_a or not Path(model_a.file_path).exists():
            raise FileNotFoundError(f"Model A '{model_a_id}' not found.")
        if not model_b or not Path(model_b.file_path).exists():
            raise FileNotFoundError(f"Model B '{model_b_id}' not found.")

        # Create isolated ONNX inference sessions
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        sess_a = ort.InferenceSession(model_a.file_path, sess_options=opts, providers=["CPUExecutionProvider"])
        sess_b = ort.InferenceSession(model_b.file_path, sess_options=opts, providers=["CPUExecutionProvider"])

        input_a = sess_a.get_inputs()[0].name
        input_b = sess_b.get_inputs()[0].name

        # Synthesize representative deterministic benchmark sequences: shape (1, 30, 166)
        np.random.seed(42)
        test_samples = [np.random.randn(1, 30, 166).astype(np.float32) for _ in range(iterations)]

        # 1. Warm-up
        for _ in range(5):
            sess_a.run(None, {input_a: test_samples[0]})
            sess_b.run(None, {input_b: test_samples[0]})

        # 2. Benchmark Model A
        latencies_a: List[float] = []
        outputs_a: List[int] = []
        for sample in test_samples:
            t0 = time.perf_counter()
            out = sess_a.run(None, {input_a: sample})[0]
            latencies_a.append((time.perf_counter() - t0) * 1000.0)
            outputs_a.append(int(np.argmax(out[0])))

        # 3. Benchmark Model B
        latencies_b: List[float] = []
        outputs_b: List[int] = []
        for sample in test_samples:
            t0 = time.perf_counter()
            out = sess_b.run(None, {input_b: sample})[0]
            latencies_b.append((time.perf_counter() - t0) * 1000.0)
            outputs_b.append(int(np.argmax(out[0])))

        # 4. Agreement calculation
        matches = sum(1 for a, b in zip(outputs_a, outputs_b) if a == b)
        agreement_pct = round((matches / iterations) * 100.0, 2)

        # 5. File size comparison
        size_a = Path(model_a.file_path).stat().st_size
        size_b = Path(model_b.file_path).stat().st_size
        size_reduction_pct = round(((size_a - size_b) / size_a) * 100.0, 2) if size_a > 0 else 0.0

        p50_a = round(float(np.percentile(latencies_a, 50)), 3)
        p50_b = round(float(np.percentile(latencies_b, 50)), 3)
        speedup = round(p50_a / p50_b, 2) if p50_b > 0 else 1.0

        return {
            "comparison": f"{model_a_id} vs {model_b_id}",
            "iterations": iterations,
            "model_a": {
                "id": model_a_id,
                "name": model_a.name,
                "precision": model_a.precision,
                "size_bytes": size_a,
                "mean_latency_ms": round(float(np.mean(latencies_a)), 3),
                "p50_latency_ms": p50_a,
                "p95_latency_ms": round(float(np.percentile(latencies_a, 95)), 3),
            },
            "model_b": {
                "id": model_b_id,
                "name": model_b.name,
                "precision": model_b.precision,
                "size_bytes": size_b,
                "mean_latency_ms": round(float(np.mean(latencies_b)), 3),
                "p50_latency_ms": p50_b,
                "p95_latency_ms": round(float(np.percentile(latencies_b, 95)), 3),
            },
            "agreement_percentage": agreement_pct,
            "size_reduction_percentage": size_reduction_pct,
            "speedup_factor": speedup,
            "recommendation": (
                f"Model '{model_b_id}' achieves {agreement_pct}% output agreement with {size_reduction_pct}% smaller footprint."
                if agreement_pct >= 90.0 else f"Model '{model_a_id}' exhibits higher stability."
            ),
        }


ab_evaluator = ModelABEvaluator()
