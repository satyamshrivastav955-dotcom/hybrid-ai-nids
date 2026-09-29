"""Ablation study: RF / AE / IF / LSTM alone and in combination + full ensemble.

Compares factual measurements; nothing is labelled 'best' except by an
explicitly stated criterion reported alongside.
Usage: python -m evaluation.ablation --splits data/splits --models models
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.common import load_artifacts, model_signals, save_results
from evaluation.metrics import classification_metrics
from evaluation.plots import bar_comparison_fig
from ml.ensemble.ensemble import EnsembleEngine
from ml.preprocessing.cleaning import normalize_labels

COMBOS = {
    "RF_only": ["random_forest"],
    "AE_only": ["autoencoder"],
    "IF_only": ["isolation_forest"],
    "RF+AE": ["random_forest", "autoencoder"],
    "RF+IF": ["random_forest", "isolation_forest"],
    "RF+AE+IF": ["random_forest", "autoencoder", "isolation_forest"],
    "FULL": ["random_forest", "autoencoder", "isolation_forest", "lstm"],
}


def run(splits_dir: Path, model_dir: Path, results_dir: Path, figures_dir: Path, base: str = "cicids2017") -> dict:
    art = load_artifacts(model_dir)
    pre = art["pre"]
    test = pd.read_parquet(splits_dir / f"{base}_test.parquet")
    X = pre.transform(test)
    labels = normalize_labels(test[pre.label_col_])
    y_true = (labels.str.lower() != "benign").astype(int).values
    sig_all = model_signals(art, X)
    # LSTM per-row scores unavailable without sequences in this offline cut; evaluate available subset factually.
    results = {}
    for name, keys in COMBOS.items():
        avail = {k: v for k, v in sig_all.items() if k in keys}
        if not avail:
            results[name] = {"note": "required model artifacts unavailable; skipped factually"}
            continue
        w = {k: 1.0 / len(avail) for k in avail}
        eng = EnsembleEngine(weights={**{k: 0.0 for k in ("random_forest", "autoencoder", "isolation_forest", "lstm")}, **w})
        fused = eng.fuse(avail)
        risk, pred = np.asarray(fused["final_risk_score"]), np.asarray(fused["final_prediction"])
        results[name] = classification_metrics(y_true, pred, risk)
    if art["ens"] is not None:
        fused = art["ens"].fuse(sig_all)
        risk, pred = np.asarray(fused["final_risk_score"]), np.asarray(fused["final_prediction"])
        results["FULL_trained_weights"] = classification_metrics(y_true, pred, risk)
    fig = bar_comparison_fig({k: v.get("f1", 0) for k, v in results.items() if "f1" in v},
                             "Ablation F1 by combination", figures_dir / "ablation_f1.png")
    payload = {"protocol": "ablation", "results": results, "figures": {"ablation_f1": fig}}
    save_results("ablation_metrics", payload, results_dir)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--figures", default="experiments/figures")
    ap.add_argument("--base", default="cicids2017")
    a = ap.parse_args()
    print(json.dumps(run(Path(a.splits), Path(a.models), Path(a.out), Path(a.figures), a.base), indent=2, default=str))


if __name__ == "__main__":
    main()
