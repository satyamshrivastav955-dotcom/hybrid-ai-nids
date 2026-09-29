"""Drift experiment: baseline vs shifted-window performance + PSI.

Usage: python -m evaluation.drift --splits data/splits --models models
Controlled shift: compares val (reference) vs test (current) distributions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.common import load_artifacts, model_signals, save_results
from evaluation.metrics import classification_metrics
from ml.drift.psi import compute_drift
from ml.preprocessing.cleaning import normalize_labels


def run(splits_dir: Path, model_dir: Path, results_dir: Path, base: str = "cicids2017") -> dict:
    art = load_artifacts(model_dir)
    pre = art["pre"]
    ref = pd.read_parquet(splits_dir / f"{base}_val.parquet")
    cur = pd.read_parquet(splits_dir / f"{base}_test.parquet")
    X_ref, X_cur = pre.transform(ref), pre.transform(cur)
    drift = compute_drift(pd.DataFrame(X_ref, columns=pre.feature_names_),
                          pd.DataFrame(X_cur, columns=pre.feature_names_),
                          features=pre.feature_names_)
    perf = {}
    for name, df, X in (("reference(val)", ref, X_ref), ("current(test)", cur, X_cur)):
        labels = normalize_labels(df[pre.label_col_])
        y_true = (labels.str.lower() != "benign").astype(int).values
        sig = model_signals(art, X)
        if art["ens"] is not None:
            fused = art["ens"].fuse(sig)
            risk, pred = np.asarray(fused["final_risk_score"]), np.asarray(fused["final_prediction"])
        else:
            risk = np.asarray(sig["random_forest"])
            pred = (risk >= 0.5).astype(int)
        perf[name] = classification_metrics(y_true, pred, risk)
    payload = {"protocol": "drift", "drift": drift, "performance": perf,
               "note": "Only measured values are reported; no improvement is claimed without a recalibration run."}
    save_results("drift_metrics", payload, results_dir)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--base", default="cicids2017")
    a = ap.parse_args()
    print(json.dumps(run(Path(a.splits), Path(a.models), Path(a.out), a.base), indent=2, default=str))


if __name__ == "__main__":
    main()
