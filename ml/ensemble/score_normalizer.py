"""Score normalisation: map heterogeneous model outputs to a common 0..1 scale.

  RF attack probability : 1 - P(benign) from multiclass predict_proba.
  Autoencoder           : threshold-anchored normalisation (see model).
  Isolation Forest      : benign-val min-max mapped decision score.
  LSTM                  : sigmoid sequence probability (already 0..1).

This module documents and validates the contract; per-model scaling lives
with each model and is fitted on VALIDATION data only.
"""
from __future__ import annotations

import numpy as np


MODEL_KEYS = ("random_forest", "autoencoder", "isolation_forest", "lstm")


def rf_attack_probability(rf_proba: np.ndarray, benign_index: int | None) -> np.ndarray:
    p = np.asarray(rf_proba, dtype=np.float64)
    if p.ndim == 1:
        return np.clip(p, 0.0, 1.0)
    if benign_index is not None and 0 <= benign_index < p.shape[1]:
        return np.clip(1.0 - p[:, benign_index], 0.0, 1.0)
    return np.clip(1.0 - p.max(axis=1), 0.0, 1.0)


def clip01(x: np.ndarray | float) -> np.ndarray | float:
    return np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)


def validate_signals(signals: dict[str, np.ndarray | float]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for k in MODEL_KEYS:
        if k not in signals or signals[k] is None:
            continue
        v = np.asarray(signals[k], dtype=np.float64)
        if np.isnan(v).any():
            raise ValueError(f"NaN in model signal '{k}'.")
        out[k] = np.clip(v, 0.0, 1.0)
    if not out:
        raise ValueError("No model signals provided for fusion.")
    return out
