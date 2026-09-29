"""
Smart Spectator - SpectatorNet Training Orchestrator
Executes training loop, validation, early stopping, checkpointing, and test evaluation.
Conforms to Sections 26, 27, 28, 29, 31, and 52 of Phase 3 specification.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import random
import time
from typing import Dict, Any, Optional, Tuple, List
import numpy as np
import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from ai.models.spectatornet import SpectatorNet
from ai.datasets.feature_encoder import FeatureNormalizer
from ai.datasets.constants import CLASS_TO_ID, ID_TO_CLASS, DEFAULT_EVENT_CLASSES
from .config import TrainingConfig
from .dataset import SpectatorNetDataset, create_dataloader
from .losses import get_loss_function
from .metrics import compute_classification_metrics, format_confusion_matrix_ascii


def get_target_device(device_req: str) -> torch.device:
    if device_req == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    if device_req == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    if device_req == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
    return torch.device("cpu")


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class SpectatorNetTrainer:
    """Orchestrates SpectatorNet training, checkpointing, and artifact tracking."""

    def __init__(self, config: TrainingConfig):
        self.config = config
        set_seed(config.seed)
        self.device = get_target_device(config.device)

        # Setup run directory: artifacts/runs/<timestamp>_<run_name>
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"{timestamp_str}_{config.run_name}"
        self.run_dir = Path(config.artifacts_dir) / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.run_dir / "training.log"
        self._log(f"Initialized SpectatorNetTrainer (Run ID: {self.run_id}, Device: {self.device})")

    def _log(self, msg: str):
        print(f"[Trainer] {msg}")
        with open(self.log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")

    def train(self) -> Dict[str, Any]:
        cfg = self.config
        dataset_base = Path(cfg.dataset_dir)
        manifest_dir = dataset_base / "manifests"
        stats_dir = dataset_base / "statistics"

        # 1. Load Normalizer
        norm_file = stats_dir / "normalization.json"
        normalizer = FeatureNormalizer.load(str(norm_file)) if norm_file.exists() else None

        # 2. Datasets & Loaders
        train_ds = SpectatorNetDataset.from_manifest_file(
            str(manifest_dir / "train.jsonl"),
            processed_dir=str(dataset_base / "processed"),
            normalizer=normalizer,
        )
        val_ds = SpectatorNetDataset.from_manifest_file(
            str(manifest_dir / "val.jsonl"),
            processed_dir=str(dataset_base / "processed"),
            normalizer=normalizer,
        )
        test_ds = SpectatorNetDataset.from_manifest_file(
            str(manifest_dir / "test.jsonl"),
            processed_dir=str(dataset_base / "processed"),
            normalizer=normalizer,
        )

        train_loader = create_dataloader(train_ds, batch_size=cfg.batch_size, shuffle=True)
        val_loader = create_dataloader(val_ds, batch_size=cfg.batch_size, shuffle=False)
        test_loader = create_dataloader(test_ds, batch_size=cfg.batch_size, shuffle=False)

        # 3. Model Architecture
        # Infer feature dimension from first sample
        sample_x, _, _ = train_ds[0]
        feature_dim = sample_x.shape[-1]
        num_classes = len(DEFAULT_EVENT_CLASSES)

        model = SpectatorNet(
            feature_dim=feature_dim,
            hidden_dim=cfg.hidden_dim,
            num_layers=cfg.num_layers,
            num_classes=num_classes,
            bidirectional=cfg.bidirectional,
            dropout=cfg.dropout,
        ).to(self.device)

        model_info = model.get_model_info()
        self._log(f"Model parameters: {model_info['total_parameters']} ({model_info['estimated_fp32_size_mb']} MB)")

        # 4. Loss & Optimizer
        class_counts = [0] * num_classes
        for entry in train_ds.entries:
            if 0 <= entry.label_id < num_classes:
                class_counts[entry.label_id] += 1

        criterion = get_loss_function(class_counts if cfg.use_class_weights else None, device=self.device)
        optimizer = AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
        scheduler = CosineAnnealingLR(optimizer, T_max=cfg.epochs, eta_min=1e-5)

        # 5. Training Loop
        best_val_f1 = -1.0
        epochs_without_improvement = 0
        history: List[Dict[str, Any]] = []

        self._log(f"Starting training for {cfg.epochs} epochs (Patience: {cfg.early_stopping_patience})...")

        for epoch in range(1, cfg.epochs + 1):
            t0 = time.time()
            model.train()
            train_losses = []
            y_train_true = []
            y_train_pred = []

            for x_batch, y_batch, _ in train_loader:
                x_batch = x_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                optimizer.zero_grad()
                logits = model(x_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                optimizer.step()

                train_losses.append(loss.item())
                preds = torch.argmax(logits, dim=-1)
                y_train_true.extend(y_batch.cpu().numpy())
                y_train_pred.extend(preds.cpu().numpy())

            scheduler.step()
            train_loss = float(np.mean(train_losses))
            train_metrics = compute_classification_metrics(np.array(y_train_true), np.array(y_train_pred), num_classes)

            # Validation
            val_loss, val_metrics = self._evaluate(model, val_loader, criterion, num_classes)
            dur_sec = time.time() - t0

            epoch_record = {
                "epoch": epoch,
                "duration_sec": round(dur_sec, 2),
                "train_loss": round(train_loss, 4),
                "train_accuracy": train_metrics["accuracy"],
                "train_f1": train_metrics["macro_f1"],
                "val_loss": round(val_loss, 4),
                "val_accuracy": val_metrics["accuracy"],
                "val_f1": val_metrics["macro_f1"],
            }
            history.append(epoch_record)

            self._log(
                f"Epoch {epoch:02d}/{cfg.epochs} | "
                f"Train Loss: {train_loss:.4f} Acc: {train_metrics['accuracy']:.4f} F1: {train_metrics['macro_f1']:.4f} | "
                f"Val Loss: {val_loss:.4f} Acc: {val_metrics['accuracy']:.4f} F1: {val_metrics['macro_f1']:.4f} "
                f"({dur_sec:.1f}s)"
            )

            # Checkpoint Best Model
            if val_metrics["macro_f1"] > best_val_f1:
                best_val_f1 = val_metrics["macro_f1"]
                epochs_without_improvement = 0
                torch.save(
                    {
                        "model_state": model.state_dict(),
                        "epoch": epoch,
                        "val_metrics": val_metrics,
                        "config": cfg.to_dict(),
                        "feature_dim": feature_dim,
                    },
                    self.run_dir / "best_checkpoint.pt",
                )
                self._log(f"  ⭐ New best validation Macro F1: {best_val_f1:.4f} (Saved best_checkpoint.pt)")
            else:
                epochs_without_improvement += 1
                if epochs_without_improvement >= cfg.early_stopping_patience:
                    self._log(f"Early stopping triggered after {epoch} epochs.")
                    break

        # Save latest checkpoint
        torch.save(
            {
                "model_state": model.state_dict(),
                "epoch": epoch,
                "config": cfg.to_dict(),
                "feature_dim": feature_dim,
            },
            self.run_dir / "latest_checkpoint.pt",
        )

        # 6. Final Evaluation on Blind Test Set
        self._log("\nEvaluating best checkpoint on held-out test split...")
        best_ckpt = torch.load(self.run_dir / "best_checkpoint.pt", map_location=self.device)
        model.load_state_dict(best_ckpt["model_state"])
        test_loss, test_metrics = self._evaluate(model, test_loader, criterion, num_classes)

        self._log(f"✔ Final Test Accuracy:  {test_metrics['accuracy']:.4f}")
        self._log(f"✔ Final Test Macro F1:  {test_metrics['macro_f1']:.4f}")
        self._log(f"✔ Final Test Weighted F1:{test_metrics['weighted_f1']:.4f}")

        ascii_cm = format_confusion_matrix_ascii(test_metrics["confusion_matrix"], DEFAULT_EVENT_CLASSES)
        self._log("\nConfusion Matrix on Held-Out Test Set:\n" + ascii_cm)

        # 7. Save Run Artifacts
        run_results = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "config": cfg.to_dict(),
            "model_info": model_info,
            "best_val_f1": best_val_f1,
            "test_loss": test_loss,
            "test_metrics": test_metrics,
            "history": history,
        }

        with open(self.run_dir / "config.json", "w") as f:
            json.dump(cfg.to_dict(), f, indent=2)
        with open(self.run_dir / "metrics.json", "w") as f:
            json.dump(run_results, f, indent=2)
        with open(self.run_dir / "label_map.json", "w") as f:
            json.dump({"class_to_id": CLASS_TO_ID, "id_to_class": ID_TO_CLASS}, f, indent=2)

        # Copy normalization parameters to run directory for self-contained deployment
        if norm_file.exists():
            import shutil
            shutil.copy(norm_file, self.run_dir / "normalization.json")

        schema_file = stats_dir / "feature_schema.json"
        if schema_file.exists():
            import shutil
            shutil.copy(schema_file, self.run_dir / "feature_schema.json")

        self._log(f"All run artifacts saved successfully in '{self.run_dir}'")
        return run_results

    def _evaluate(
        self,
        model: SpectatorNet,
        dataloader,
        criterion,
        num_classes: int,
    ) -> Tuple[float, Dict[str, Any]]:
        model.eval()
        losses = []
        y_true = []
        y_pred = []

        with torch.no_grad():
            for x_batch, y_batch, _ in dataloader:
                x_batch = x_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                logits = model(x_batch)
                loss = criterion(logits, y_batch)
                losses.append(loss.item())

                preds = torch.argmax(logits, dim=-1)
                y_true.extend(y_batch.cpu().numpy())
                y_pred.extend(preds.cpu().numpy())

        avg_loss = float(np.mean(losses)) if losses else 0.0
        metrics = compute_classification_metrics(np.array(y_true), np.array(y_pred), num_classes)
        return avg_loss, metrics
