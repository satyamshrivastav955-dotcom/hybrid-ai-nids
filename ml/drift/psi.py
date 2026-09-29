"""Population Stability Index (PSI) drift monitoring.

PSI(reference || current) per feature over quantile bins learned on the
REFERENCE distribution; aggregate = mean (configurable to max).

PSI < 0.1            -> STABLE
0.1 <= PSI < 0.25    -> MODERATE drift
PSI >= 0.25          -> SEVERE drift

PSI never mutates model thresholds by itself. It emits drift events; an
explicit, auditable recalibration/retraining policy consumes them.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class FeaturePSI:
    feature: str
    psi: float
    status: str


def _bin_edges(ref: pd.Series, n_bins: int) -> np.ndarray:
    q = np.linspace(0, 100, n_bins + 1)
    edges = np.unique(np.percentile(ref.dropna().values, q))
    if len(edges) < 3:
        lo, hi = float(ref.min()), float(ref.max())
        if lo == hi:
            lo, hi = lo - 0.5, hi + 0.5
        edges = np.linspace(lo, hi, n_bins + 1)
    # expand outer edges so out-of-range current values fall inside
    edges[0], edges[-1] = -np.inf, np.inf
    return edges


def psi_for_feature(ref: pd.Series, cur: pd.Series, n_bins: int = 10, epsilon: float = 1e-4) -> float:
    ref = pd.to_numeric(ref, errors="coerce").dropna()
    cur = pd.to_numeric(cur, errors="coerce").dropna()
    if len(ref) == 0 or len(cur) == 0:
        return 0.0
    edges = _bin_edges(ref, n_bins)
    r_counts, _ = np.histogram(ref.values, bins=edges)
    c_counts, _ = np.histogram(cur.values, bins=edges)
    r_pct = np.clip(r_counts / max(1, r_counts.sum()), epsilon, 1.0)
    c_pct = np.clip(c_counts / max(1, c_counts.sum()), epsilon, 1.0)
    # renormalise after clipping for stability
    r_pct, c_pct = r_pct / r_pct.sum(), c_pct / c_pct.sum()
    return float(np.sum((c_pct - r_pct) * np.log(c_pct / r_pct)))


def classify_psi(psi: float, moderate: float = 0.1, severe: float = 0.25) -> str:
    if psi >= severe:
        return "SEVERE"
    if psi >= moderate:
        return "MODERATE"
    return "STABLE"


def compute_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    features: list[str] | None = None,
    n_bins: int = 10,
    epsilon: float = 1e-4,
    moderate_threshold: float = 0.1,
    severe_threshold: float = 0.25,
    aggregate: str = "mean",
    reference_version: str = "baseline-v1",
) -> dict:
    features = features or [c for c in reference.columns if c in current.columns]
    rows = []
    for f in features:
        v = psi_for_feature(reference[f], current[f], n_bins, epsilon)
        rows.append(FeaturePSI(f, round(v, 4), classify_psi(v, moderate_threshold, severe_threshold)))
    agg = float(np.mean([r.psi for r in rows])) if rows else 0.0
    if aggregate == "max":
        agg = float(max([r.psi for r in rows])) if rows else 0.0
    overall = classify_psi(agg, moderate_threshold, severe_threshold)
    return {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "reference_version": reference_version,
        "current_rows": int(len(current)),
        "reference_rows": int(len(reference)),
        "aggregate_psi": round(agg, 4),
        "status": overall,
        "features": [{"feature": r.feature, "psi": r.psi, "status": r.status} for r in rows],
        "adaptation": {
            "threshold_changed": False,
            "action": ("investigate + consider recalibration" if overall != "STABLE"
                       else "none"),
            "note": "PSI is advisory only; adaptation requires an explicit audited action.",
        },
    }
