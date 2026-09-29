"""Explainability: RF importances/SHAP-style attributions + anomaly contributions.

No fabricated explanations: every contribution is computed from fitted model
state and the actual input row.
"""
from __future__ import annotations

import numpy as np


def rf_top_features(importances: np.ndarray, feature_names: list[str], x_row: np.ndarray,
                    top_n: int = 5) -> list[dict]:
    imp = np.asarray(importances, dtype=float)
    x = np.asarray(x_row, dtype=float)
    # Contribution proxy: importance weighted by |standardised value| (documented heuristic).
    contrib = imp * np.abs(x)
    idx = np.argsort(contrib)[::-1][:top_n]
    total = contrib[idx].sum() or 1.0
    return [{"feature": feature_names[i], "contribution": round(float(contrib[i] / total), 4),
             "value": round(float(x[i]), 4)} for i in idx]


def anomaly_top_features(per_feature_error: np.ndarray, feature_names: list[str],
                         top_n: int = 5) -> list[dict]:
    err = np.asarray(per_feature_error, dtype=float)
    idx = np.argsort(err)[::-1][:top_n]
    total = err[idx].sum() or 1.0
    return [{"feature": feature_names[i], "contribution": round(float(err[i] / total), 4),
             "error": round(float(err[i]), 6)} for i in idx]


def shap_top_features(shap_values: np.ndarray, feature_names: list[str], top_n: int = 5) -> list[dict]:
    sv = np.asarray(shap_values, dtype=float)
    if sv.ndim > 1:
        sv = np.abs(sv).mean(axis=0)
    else:
        sv = np.abs(sv)
    idx = np.argsort(sv)[::-1][:top_n]
    total = sv[idx].sum() or 1.0
    return [{"feature": feature_names[i], "contribution": round(float(sv[i] / total), 4)} for i in idx]
