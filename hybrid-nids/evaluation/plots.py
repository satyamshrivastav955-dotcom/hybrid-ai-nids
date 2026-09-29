"""Reproducible matplotlib figures for research (no seaborn dependency)."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _save(fig, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def confusion_matrix_fig(cm: np.ndarray, labels: list[str], path: Path) -> str:
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix")
    fig.colorbar(im, ax=ax)
    return _save(fig, path)


def roc_curve_fig(y_true: np.ndarray, y_score: np.ndarray, path: Path) -> str:
    from sklearn.metrics import roc_curve, auc
    fpr, tpr, _ = roc_curve(y_true, y_score)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, label=f"AUC={auc(fpr, tpr):.3f}")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray")
    ax.set_xlabel("FPR")
    ax.set_ylabel("TPR")
    ax.set_title("ROC Curve")
    ax.legend()
    return _save(fig, path)


def pr_curve_fig(y_true: np.ndarray, y_score: np.ndarray, path: Path) -> str:
    from sklearn.metrics import precision_recall_curve, average_precision_score
    p, r, _ = precision_recall_curve(y_true, y_score)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(r, p, label=f"AP={average_precision_score(y_true, y_score):.3f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve")
    ax.legend()
    return _save(fig, path)


def bar_comparison_fig(groups: dict[str, float], title: str, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(list(groups.keys()), list(groups.values()))
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=30)
    return _save(fig, path)


def psi_timeline_fig(history: list[dict], path: Path) -> str:
    xs = list(range(len(history)))
    ys = [h.get("aggregate_psi", 0) for h in history]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(xs, ys, marker="o")
    ax.axhline(0.1, linestyle="--", color="orange", label="moderate=0.1")
    ax.axhline(0.25, linestyle="--", color="red", label="severe=0.25")
    ax.set_xlabel("Window")
    ax.set_ylabel("Aggregate PSI")
    ax.set_title("PSI Timeline")
    ax.legend()
    return _save(fig, path)


def score_hist_fig(benign_scores: np.ndarray, attack_scores: np.ndarray, threshold: float, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(np.asarray(benign_scores), bins=50, alpha=0.6, label="benign")
    ax.hist(np.asarray(attack_scores), bins=50, alpha=0.6, label="attack")
    ax.axvline(threshold, color="red", linestyle="--", label=f"threshold={threshold:.4f}")
    ax.set_title("Anomaly Score Distribution")
    ax.legend()
    return _save(fig, path)


def calibration_curve_fig(y_true: np.ndarray, y_score: np.ndarray, path: Path, n_bins: int = 10) -> str:
    from sklearn.calibration import calibration_curve
    prob_true, prob_pred = calibration_curve(y_true, y_score, n_bins=n_bins)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(prob_pred, prob_true, marker="o", label="model")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="perfectly calibrated")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title("Calibration Curve")
    ax.legend()
    return _save(fig, path)
