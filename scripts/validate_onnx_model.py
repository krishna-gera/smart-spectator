#!/usr/bin/env python3
"""
Smart Spectator - ONNX Model Validator
Validates exported ONNX model against ONNX Runtime and reports tensor shapes & latency.
"""

import sys
import time
from pathlib import Path
import numpy as np
import onnxruntime as ort

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def validate_onnx(model_path: str = "ai/models/yolov8n.onnx"):
    print(f"=== Validating ONNX Model: '{model_path}' ===")
    if not Path(model_path).exists():
        print(f"❌ Model file '{model_path}' does not exist.")
        sys.exit(1)

    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    
    # 1. Inspect Inputs
    inputs = session.get_inputs()
    print("Inputs:")
    for inp in inputs:
        print(f"  - Name: '{inp.name}', Shape: {inp.shape}, Type: {inp.type}")

    # 2. Inspect Outputs
    outputs = session.get_outputs()
    print("Outputs:")
    for out in outputs:
        print(f"  - Name: '{out.name}', Shape: {out.shape}, Type: {out.type}")

    # 3. Dry-run inference
    print("\nRunning test forward pass with synthetic image [1, 3, 640, 640]...")
    dummy_img = np.random.rand(1, 3, 640, 640).astype(np.float32)
    
    t0 = time.perf_counter()
    preds = session.run([outputs[0].name], {inputs[0].name: dummy_img})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    output_shape = preds[0].shape
    print(f"✔ Forward pass succeeded in {elapsed_ms:.2f} ms!")
    print(f"✔ Output tensor shape: {output_shape}")
    assert output_shape[1] == 84
    assert output_shape[2] == 8400
    print("✔ Model schema strictly adheres to YOLOv8 [1, 84, 8400] standard!")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "ai/models/yolov8n.onnx"
    validate_onnx(path)
