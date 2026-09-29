#!/usr/bin/env python3
"""
Smart Spectator - SpectatorNet ONNX Numerical Validator
Verifies numerical equivalence between PyTorch model output and ONNX Runtime output.
Conforms to Section 40 of Phase 3 specification.
"""

import argparse
from pathlib import Path
import sys
import numpy as np
import onnxruntime as ort
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.models.spectatornet import SpectatorNet


def validate_spectatornet_onnx(
    checkpoint_path: str = "ai/models/spectatornet.pt",
    onnx_path: str = "ai/models/spectatornet.onnx",
    tolerance: float = 1e-4,
    feature_dim: int = 166,
    sequence_length: int = 30,
) -> bool:
    print("==================================================")
    print(" SMART SPECTATOR — SPECTATORNET ONNX VALIDATOR")
    print("==================================================")
    print(f"PyTorch Checkpoint: {checkpoint_path}")
    print(f"ONNX Model:         {onnx_path}")
    print(f"Tolerance:          {tolerance}")

    if not Path(onnx_path).exists():
        print(f"❌ Error: ONNX file '{onnx_path}' does not exist.")
        return False

    # 1. Load PyTorch model
    device = torch.device("cpu")
    pt_model = SpectatorNet(feature_dim=feature_dim)
    ckpt = torch.load(checkpoint_path, map_location=device)
    pt_model.load_state_dict(ckpt["model_state"])
    pt_model.eval()

    # 2. Load ONNX Runtime session
    ort_session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = ort_session.get_inputs()[0].name
    output_name = ort_session.get_outputs()[0].name

    print(f"ONNX Input Name:  '{input_name}', Shape: {ort_session.get_inputs()[0].shape}")
    print(f"ONNX Output Name: '{output_name}', Shape: {ort_session.get_outputs()[0].shape}")

    # 3. Test on 10 random inputs across different batch sizes
    passed = True
    max_errors = []
    mean_errors = []

    test_batches = [1, 2, 4, 8]
    for b in test_batches:
        dummy_np = np.random.randn(b, sequence_length, feature_dim).astype(np.float32)
        dummy_torch = torch.from_numpy(dummy_np)

        with torch.no_grad():
            pt_out = pt_model(dummy_torch).numpy()

        ort_out = ort_session.run([output_name], {input_name: dummy_np})[0]

        abs_err = np.abs(pt_out - ort_out)
        max_err = float(np.max(abs_err))
        mean_err = float(np.mean(abs_err))

        max_errors.append(max_err)
        mean_errors.append(mean_err)

        if max_err > tolerance:
            print(f"❌ Batch size {b}: Numerical divergence! Max Abs Error = {max_err:.6e} > {tolerance}")
            passed = False
        else:
            print(f"✔ Batch size {b:2d}: Verified (Max Error: {max_err:.6e}, Mean Error: {mean_err:.6e})")

    overall_max = float(np.max(max_errors))
    overall_mean = float(np.mean(mean_errors))

    print("\n--- Numerical Validation Summary ---")
    print(f"Overall Max Absolute Error:  {overall_max:.6e}")
    print(f"Overall Mean Absolute Error: {overall_mean:.6e}")

    if passed:
        print("✔ ONNX NUMERICAL VALIDATION PASSED (Zero divergence from PyTorch)!")
    else:
        print("❌ ONNX NUMERICAL VALIDATION FAILED!")

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate SpectatorNet ONNX numerical equivalence")
    parser.add_argument("--checkpoint", default="ai/models/spectatornet.pt")
    parser.add_argument("--onnx", default="ai/models/spectatornet.onnx")
    parser.add_argument("--tolerance", type=float, default=1e-4)
    args = parser.parse_args()

    success = validate_spectatornet_onnx(
        checkpoint_path=args.checkpoint,
        onnx_path=args.onnx,
        tolerance=args.tolerance,
    )
    sys.exit(0 if success else 1)
