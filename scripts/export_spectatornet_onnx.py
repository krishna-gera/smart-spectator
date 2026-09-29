#!/usr/bin/env python3
"""
Smart Spectator - SpectatorNet ONNX Model Exporter
Exports PyTorch checkpoint to optimized ONNX graph with dynamic batch support.
Conforms to Section 39 of Phase 3 specification.
"""

import argparse
from pathlib import Path
import sys
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.models.spectatornet import SpectatorNet


def export_spectatornet_onnx(
    checkpoint_path: str = "ai/models/spectatornet.pt",
    output_onnx_path: str = "ai/models/spectatornet.onnx",
    feature_dim: int = 166,
    sequence_length: int = 30,
):
    print("==================================================")
    print(" SMART SPECTATOR — SPECTATORNET ONNX EXPORT")
    print("==================================================")
    print(f"Checkpoint:   {checkpoint_path}")
    print(f"Output ONNX:  {output_onnx_path}")
    print(f"Tensor Shape: [batch_size, {sequence_length}, {feature_dim}]")

    device = torch.device("cpu")
    model = SpectatorNet(feature_dim=feature_dim)
    ckpt = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    dummy_input = torch.randn(1, sequence_length, feature_dim, dtype=torch.float32)

    out_path = Path(output_onnx_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        str(out_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["temporal_features"],
        output_names=["event_logits"],
        dynamic_axes={
            "temporal_features": {0: "batch_size"},
            "event_logits": {0: "batch_size"},
        },
        dynamo=False,
    )

    size_mb = out_path.stat().st_size / (1024.0 * 1024.0)
    print(f"✔ Model successfully exported to '{out_path}' ({size_mb:.2f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export SpectatorNet to ONNX")
    parser.add_argument("--checkpoint", default="ai/models/spectatornet.pt")
    parser.add_argument("--output", default="ai/models/spectatornet.onnx")
    parser.add_argument("--feature-dim", type=int, default=166)
    parser.add_argument("--seq-len", type=int, default=30)
    args = parser.parse_args()

    export_spectatornet_onnx(
        checkpoint_path=args.checkpoint,
        output_onnx_path=args.output,
        feature_dim=args.feature_dim,
        sequence_length=args.seq_len,
    )
