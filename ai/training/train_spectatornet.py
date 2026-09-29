#!/usr/bin/env python3
"""
Smart Spectator - SpectatorNet Training CLI Script
Usage:
    python ai/training/train_spectatornet.py --epochs 25 --batch-size 16
"""

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ai.training.config import TrainingConfig
from ai.training.trainer import SpectatorNetTrainer


def main():
    parser = argparse.ArgumentParser(description="Train SpectatorNet Temporal Event Model")
    parser.add_argument("--run-name", default="spectatornet_gru_v1")
    parser.add_argument("--dataset-dir", default="ai/datasets/smart_spectator")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    config = TrainingConfig(
        run_name=args.run_name,
        dataset_dir=args.dataset_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        hidden_dim=args.hidden_dim,
        early_stopping_patience=args.patience,
        seed=args.seed,
        device=args.device,
    )

    trainer = SpectatorNetTrainer(config)
    results = trainer.train()
    print(f"\n✔ Training completed! Best Val Macro F1: {results['best_val_f1']:.4f}")
    print(f"✔ Test Macro F1: {results['test_metrics']['macro_f1']:.4f}")


if __name__ == "__main__":
    main()
