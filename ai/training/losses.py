"""
Smart Spectator - Training Loss Functions
Implements CrossEntropyLoss with optional inverse-frequency class weights.
Conforms to Section 30 of Phase 3 specification.
"""

from typing import Optional, List
import numpy as np
import torch
import torch.nn as nn


def get_loss_function(class_counts: Optional[List[int]] = None, device: torch.device = torch.device("cpu")) -> nn.Module:
    """Returns CrossEntropyLoss, applying inverse class frequency weights if class counts provided."""
    if class_counts and sum(class_counts) > 0:
        total = sum(class_counts)
        num_classes = len(class_counts)
        weights = [
            float(total / (num_classes * max(1, count))) for count in class_counts
        ]
        # Normalize weights
        norm_weights = np.array(weights, dtype=np.float32)
        norm_weights = norm_weights / np.mean(norm_weights)
        weight_tensor = torch.tensor(norm_weights, dtype=torch.float32, device=device)
        return nn.CrossEntropyLoss(weight=weight_tensor)
    return nn.CrossEntropyLoss()
