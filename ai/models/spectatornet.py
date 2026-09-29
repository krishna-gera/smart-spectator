"""
Smart Spectator - SpectatorNet Lightweight Temporal Neural Network
Architecture: Feature Projection -> Bidirectional GRU -> Temporal Attention -> Classifier.
Conforms to Sections 23, 24, 25, and 38 of Phase 3 specification.
Engineered for Snapdragon Hexagon NPU & low-power edge execution.
"""

from typing import Dict, Any, Tuple, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F

from ai.datasets.constants import DEFAULT_EVENT_CLASSES, ID_TO_CLASS


class TemporalAttention(nn.Module):
    """Calculates temporal attention weights across sequence timesteps."""

    def __init__(self, hidden_dim: int):
        super().__init__()
        self.attn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1, bias=False),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # x shape: [B, T, H]
        scores = self.attn(x)  # [B, T, 1]
        weights = F.softmax(scores, dim=1)  # [B, T, 1]
        context = torch.sum(x * weights, dim=1)  # [B, H]
        return context, weights.squeeze(-1)


class SpectatorNet(nn.Module):
    """
    SpectatorNet Level 3 Temporal Event Classifier.
    Consumes [batch, sequence_length, feature_dim] structured observation features
    and emits multi-class event logits.
    """

    def __init__(
        self,
        feature_dim: int = 166,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_classes: int = len(DEFAULT_EVENT_CLASSES),
        bidirectional: bool = True,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.feature_dim = feature_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.bidirectional = bidirectional
        self.directions = 2 if bidirectional else 1

        # 1. Feature Projection Block
        self.projection = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )

        # 2. Recurrent Temporal Modeling (GRU)
        self.gru = nn.GRU(
            input_size=hidden_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        gru_out_dim = hidden_dim * self.directions

        # 3. Temporal Attention Pooling
        self.attention = TemporalAttention(gru_out_dim)

        # 4. Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(gru_out_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: Input tensor [Batch, Sequence_Length, Feature_Dim]
        Returns:
            Logits tensor [Batch, Num_Classes]
        """
        # Feature projection: [B, T, D] -> [B, T, H]
        proj = self.projection(x)

        # Temporal GRU: [B, T, H] -> [B, T, H * directions]
        gru_out, _ = self.gru(proj)

        # Attention pooling: [B, T, H * directions] -> [B, H * directions]
        context, _ = self.attention(gru_out)

        # Classification logits: [B, Num_Classes]
        logits = self.classifier(context)
        return logits

    def predict_proba(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Inference helper returning softmax probabilities and class predictions."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = F.softmax(logits, dim=-1)
            preds = torch.argmax(probs, dim=-1)
        return preds, probs

    def get_model_info(self) -> Dict[str, Any]:
        """Returns parameter count, memory estimate, and architecture configuration."""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        # FP32 size in MB = params * 4 bytes / 1024^2
        fp32_size_mb = (total_params * 4.0) / (1024.0 * 1024.0)

        return {
            "model_name": "SpectatorNet-GRU",
            "version": "1.0.0",
            "feature_dim": self.feature_dim,
            "hidden_dim": self.hidden_dim,
            "num_layers": self.num_layers,
            "bidirectional": self.bidirectional,
            "num_classes": self.num_classes,
            "total_parameters": total_params,
            "trainable_parameters": trainable_params,
            "estimated_fp32_size_mb": round(fp32_size_mb, 2),
            "estimated_int8_size_mb": round(fp32_size_mb / 4.0, 2),
        }
