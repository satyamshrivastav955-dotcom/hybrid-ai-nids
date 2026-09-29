"""Standard classification evaluation: stratified protocol, all models + ensemble.

Usage: python -m evaluation.standard --splits data/splits --models models --out experiments/results
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from evaluation.common import benign_index, load_artifacts, model_signals, save_results
from evaluation.metrics import classification_metrics
from evaluation.plots import calibration_curve_fig, confusion_matrix_fig, pr_curve_fig, roc_curve_fig
from ml.preprocessing.cleaning import normalize_labels


def run(splits_dir: Path, model_dir: Path, results_dir: Path, figures_dir: Path, base: str = "cicids2017") -> dict:
    art = load_artifacts(model_dir)
    pre = art["pre"]
    test = pd.read_parquet(splits_dir / f"{base}_test.parquet")
    X = pre.transform(test)
    y_labels = normalize_labels(test[pre.label_col_])
    bi = benign_index(art["label_classes"])
    y_true = (y_labels.str.lower() != "benign").astype(int).values

    rf_pred = art["rf"].predict(X)
    # rf predicts encoded label ids; convert to binary via benign id
    y_pred_rf = (rf_pred != bi).astype(int)
    sig = model_signals(art, X)
    out = {"rf": classification_metrics(y_true, y_pred_rf, sig["random_forest"])}
    # Per-class quality of the supervised multiclass head (honest multiclass view).
    from sklearn.metrics import classification_report
    from evaluation.metrics import _num
    y_true_mc = pre.encode_labels(test[pre.label_col_])
    rep = classification_report(y_true_mc, np.asarray(rf_pred), output_dict=True, zero_division=0)
    per_class = {}
    for label, vals in rep.items():
        if label in ("accuracy", "macro avg", "weighted avg"):
            continue
        try:
            name = art["label_classes"][int(label)]
        except (ValueError, IndexError):
            name = str(label)
        per_class[name] = {k: (_num(v) if isinstance(v, float) else int(v))
                           for k, v in vals.items() if k in ("precision", "recall", "f1-score", "support")}
    for key, scores in sig.items():
        if key == "random_forest":
            continue
        thr = 0.5
        if key == "autoencoder" and art["ae"] is not None and art["ae"].threshold_:
            # map normalised score back is complex; use fixed 0.5 operating point and report it
            thr = 0.5
        out[key] = classification_metrics(y_true, (scores >= thr).astype(int), scores)
        out[key]["operating_threshold"] = thr
    if art["ens"] is not None:
        fused = art["ens"].fuse(sig)
        risk = np.asarray(fused["final_risk_score"])
        pred = np.asarray(fused["final_prediction"])
        out["ensemble"] = classification_metrics(y_true, pred, risk)
        out["ensemble"]["weights"] = fused["weights"]

    # Figures (ensemble if available else RF)
    figs = {}
    cm = confusion_matrix(y_true, (np.asarray(sig["random_forest"]) >= 0.5).astype(int), labels=[0, 1])
    figs["confusion_matrix"] = confusion_matrix_fig(cm, ["benign", "attack"], figures_dir / "confusion_matrix.png")
    figs["roc"] = roc_curve_fig(y_true, np.asarray(sig["random_forest"]), figures_dir / "roc_curve.png")
    figs["pr"] = pr_curve_fig(y_true, np.asarray(sig["random_forest"]), figures_dir / "pr_curve.png")
    figs["calibration"] = calibration_curve_fig(y_true, np.asarray(sig["random_forest"]), figures_dir / "calibration.png")

    payload = {"protocol": "standard_stratified", "n_test": int(len(test)),
               "label_classes": art["label_classes"], "metrics": out,
               "per_class": per_class, "figures": figs}
    save_results("standard_metrics", payload, results_dir)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--figures", default="experiments/figures")
    ap.add_argument("--base", default="cicids2017")
    a = ap.parse_args()
    payload = run(Path(a.splits), Path(a.models), Path(a.out), Path(a.figures), a.base)
    print(json.dumps(payload["metrics"], indent=2))


if __name__ == "__main__":
    main()
