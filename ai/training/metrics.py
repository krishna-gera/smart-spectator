"""
Smart Spectator - Evaluation Metrics & Confusion Matrix Utilities
Computes Accuracy, Macro Precision, Recall, Macro/Weighted F1, and Confusion Matrices.
Conforms to Sections 31 and 33 of Phase 3 specification.
"""

from typing import Dict, Any, List, Tuple
import numpy as np

from ai.datasets.constants import ID_TO_CLASS, DEFAULT_EVENT_CLASSES


def compute_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    num_classes: int = len(DEFAULT_EVENT_CLASSES),
) -> Dict[str, Any]:
    """
    Computes standard multi-class evaluation metrics without external heavy dependencies.
    """
    assert len(y_true) == len(y_pred)
    total = len(y_true)
    if total == 0:
        return {"accuracy": 0.0, "macro_f1": 0.0, "weighted_f1": 0.0}

    # Accuracy
    accuracy = float(np.sum(y_true == y_pred) / total)

    # Confusion Matrix: rows = true, cols = predicted
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1

    per_class_metrics = {}
    precisions = []
    recalls = []
    f1s = []
    supports = []

    for c in range(num_classes):
        tp = cm[c, c]
        fp = np.sum(cm[:, c]) - tp
        fn = np.sum(cm[c, :]) - tp
        support = int(np.sum(cm[c, :]))
        supports.append(support)

        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)

        class_name = ID_TO_CLASS.get(c, f"Class_{c}")
        per_class_metrics[class_name] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    macro_precision = float(np.mean(precisions))
    macro_recall = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))

    # Weighted F1
    total_support = sum(supports)
    weighted_f1 = (
        float(sum(f1 * sup for f1, sup in zip(f1s, supports)) / total_support)
        if total_support > 0
        else 0.0
    )

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_precision, 4),
        "macro_recall": round(macro_recall, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class_metrics,
        "confusion_matrix": cm.tolist(),
    }


def format_confusion_matrix_ascii(cm: List[List[int]], classes: List[str]) -> str:
    """Formats a confusion matrix as a clear text table."""
    lines = []
    header = f"{'True \\ Pred':<20}" + "".join(f"{c[:8]:>10}" for c in classes)
    lines.append(header)
    lines.append("-" * len(header))

    for i, row in enumerate(cm):
        c_name = classes[i] if i < len(classes) else f"C{i}"
        row_str = f"{c_name:<20}" + "".join(f"{val:>10}" for val in row)
        lines.append(row_str)

    return "\n".join(lines)
