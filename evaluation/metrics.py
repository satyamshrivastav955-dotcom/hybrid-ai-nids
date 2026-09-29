"""Shared classification + anomaly metrics. Single source of truth for all experiments."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, matthews_corrcoef, precision_score, recall_score,
                             roc_auc_score, average_precision_score)


def _num(x: float) -> float | None:
    v = float(x)
    if np.isnan(v) or np.isinf(v):
        return None
    return round(v, 4)


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                           y_score: np.ndarray | None = None,
                           labels: list | None = None) -> dict:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    out = {
        "accuracy": _num(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": _num(balanced_accuracy_score(y_true, y_pred)),
        "precision": _num(precision_score(y_true, y_pred, average="binary", zero_division=0)),
        "recall": _num(recall_score(y_true, y_pred, average="binary", zero_division=0)),
        "f1": _num(f1_score(y_true, y_pred, average="binary", zero_division=0)),
        "macro_f1": _num(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": _num(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "mcc": _num(matthews_corrcoef(y_true, y_pred)),
    }
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out.update({"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
                "fpr": _num(fp / max(1, fp + tn)),
                "fnr": _num(fn / max(1, fn + tp)),
                "detection_rate": _num(tp / max(1, tp + fn))})
    if y_score is not None:
        try:
            out["roc_auc"] = _num(roc_auc_score(y_true, y_score))
        except ValueError:
            out["roc_auc"] = None
        try:
            out["pr_auc"] = _num(average_precision_score(y_true, y_score))
        except ValueError:
            out["pr_auc"] = None
    return out


def summarize_runs(runs: list[dict]) -> dict:
    """Mean ± std over seeds for numeric metrics."""
    keys = [k for k, v in runs[0].items() if isinstance(v, (int, float))]
    summary = {}
    for k in keys:
        vals = np.array([r[k] for r in runs], dtype=float)
        summary[k] = {"mean": round(float(vals.mean()), 4), "std": round(float(vals.std(ddof=1)) if len(vals) > 1 else 0.0, 4),
                      "runs": [round(float(v), 4) for v in vals]}
    return summary
