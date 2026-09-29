# AI Model Lifecycle, Verification & Offline A/B Benchmarking

## 1. Principles of Edge Model Management
Smart Spectator enforces strict operational principles for AI models:
1. **Zero External Internet Access**: No remote weight downloads. All models reside locally in `ai/models/releases/`.
2. **Cryptographic Integrity Validation**: Every model file must match its known SHA-256 hash defined in `manifest.json`.
3. **Explicit Activation**: New or candidate models never supersede active production models automatically. Activation requires explicit operator instruction.
4. **Offline A/B Benchmarking**: Side-by-side performance (latency distribution, tensor output agreement, artifact footprint) must be measured locally prior to promotion.

---

## 2. Model Catalog

| Model ID | Task | Precision | Tensor Inputs | Tensor Outputs | Hardware Target |
|---|---|---|---|---|---|
| `detector_v1` | Spatial Detection | FP32 | `[1, 3, 640, 640]` | `[1, 84, 8400]` | DirectML / QNN / CPU |
| `spectatornet_v1_fp32` | Temporal Sequence | FP32 | `[1, 30, 166]` | `[1, 6]` | DirectML / CoreML / CPU |
| `spectatornet_v1_int8` | Temporal Sequence | INT8 | `[1, 30, 166]` | `[1, 6]` | Qualcomm Hexagon NPU (QNN) |

---

## 3. Offline A/B Validation Framework

The `ModelABEvaluator` benchmarks candidate models against the production baseline directly on local hardware without network dependencies:

### Evaluation Metrics
- **Mean Latency (ms)**: Average execution time per inference pass.
- **p50 / p95 Latency (ms)**: Median and 95th percentile latency figures for tail-latency assessment.
- **Agreement Percentage (%)**: Proportion of identical classification argmax outputs over a deterministic sequence of test vectors.
- **Size Reduction (%)**: Storage footprint reduction between candidate and baseline.
- **Speedup Factor**: Relative throughput ratio (`p50_baseline / p50_candidate`).

### Sample Evaluation Report
```json
{
  "comparison": "spectatornet_v1_fp32 vs spectatornet_v1_int8",
  "iterations": 50,
  "model_a": {
    "id": "spectatornet_v1_fp32",
    "precision": "FP32",
    "size_bytes": 615268,
    "mean_latency_ms": 1.45,
    "p50_latency_ms": 1.40,
    "p95_latency_ms": 1.82
  },
  "model_b": {
    "id": "spectatornet_v1_int8",
    "precision": "INT8",
    "size_bytes": 540088,
    "mean_latency_ms": 0.82,
    "p50_latency_ms": 0.79,
    "p95_latency_ms": 1.10
  },
  "agreement_percentage": 98.0,
  "size_reduction_percentage": 12.2,
  "speedup_factor": 1.77,
  "recommendation": "Model 'spectatornet_v1_int8' achieves 98.0% output agreement with 12.2% smaller footprint."
}
```
