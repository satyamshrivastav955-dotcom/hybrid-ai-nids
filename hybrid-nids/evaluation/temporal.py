"""Temporal generalisation: train on earlier traffic, test on later traffic.

Reports static-model performance per time window to quantify degradation.
Usage: python -m evaluation.temporal --splits data/splits --models models
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.common import load_artifacts, model_signals, save_results
from evaluation.metrics import classification_metrics
from ml.preprocessing.cleaning import normalize_labels


def run(splits_dir: Path, model_dir: Path, results_dir: Path, base: str = "cicids2017_temporal") -> dict:
    meta_path = splits_dir / f"{base}_meta.json"
    if not meta_path.exists():
        base = "cicids2017"
    art = load_artifacts(model_dir)
    pre = art["pre"]
    out: dict = {"protocol": "temporal", "windows": {}}
    for split in ("train", "val", "test"):
        df = pd.read_parquet(splits_dir / f"{base}_{split}.parquet")
        X = pre.transform(df)
        labels = normalize_labels(df[pre.label_col_])
        y_true = (labels.str.lower() != "benign").astype(int).values
        sig = model_signals(art, X)
        if art["ens"] is not None:
            fused = art["ens"].fuse(sig)
            risk, pred = np.asarray(fused["final_risk_score"]), np.asarray(fused["final_prediction"])
        else:
            risk = np.asarray(sig["random_forest"])
            pred = (risk >= 0.5).astype(int)
        out["windows"][split] = {"n": int(len(df)), **classification_metrics(y_true, pred, risk)}
    save_results("temporal_metrics", out, results_dir)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--base", default="cicids2017_temporal")
    a = ap.parse_args()
    print(json.dumps(run(Path(a.splits), Path(a.models), Path(a.out), a.base), indent=2, default=str))


if __name__ == "__main__":
    main()
