"""LSTM sequence-level evaluation on the chronologically-ordered temporal test split.

Answers RQ4 directly: how well does the temporal model score ordered flow
windows? Uses the same sequence construction as training (timestamp order,
optional src/dst context). Saves experiments/results/lstm_metrics.json.

Usage: python scripts/evaluate_lstm.py --splits data/splits --models models
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.common import benign_index, load_artifacts, save_results  # noqa: E402
from evaluation.metrics import classification_metrics  # noqa: E402
from ml.common import load_yaml  # noqa: E402
from ml.models.sequencing import build_sequences  # noqa: E402
from ml.preprocessing.cleaning import normalize_labels  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--base", default="cicids2017_temporal")
    ap.add_argument("--split", default="test")
    a = ap.parse_args()
    import os
    os.chdir(Path(__file__).resolve().parents[1])

    art = load_artifacts(Path(a.models))
    if art["lstm"] is None:
        raise SystemExit("No LSTM artifact in model dir.")
    lstm = art["lstm"]
    pre = art["pre"]
    cfg = load_yaml("configs/models.yaml").get("lstm", {})
    ts_col = cfg.get("timestamp_column", "Timestamp")
    seq_keys = cfg.get("sequence_keys", [])

    df = pd.read_parquet(Path(a.splits) / f"{a.base}_{a.split}.parquet")
    X = pre.transform(df)
    labels = normalize_labels(df[pre.label_col_])
    bi = benign_index(art["label_classes"])
    yb = (pre.encode_labels(df[pre.label_col_]) != bi).astype(int)
    ts = df[ts_col] if ts_col in df.columns else None
    grp = None
    if seq_keys and all(k in df.columns for k in seq_keys):
        grp = df[seq_keys].astype(str).agg("|".join, axis=1)
    Xs, ys = build_sequences(X, yb, timestamps=ts, groups=grp, seq_len=lstm.seq_len)
    print(f"sequences: {len(Xs)} (from {len(df)} flows)")
    if len(Xs) == 0:
        raise SystemExit("No sequences built.")
    scores = lstm.predict_proba(Xs)
    pred = (scores >= 0.5).astype(int)
    metrics = classification_metrics(np.asarray(ys), pred, scores)
    metrics["n_sequences"] = int(len(Xs))
    metrics["operating_threshold"] = 0.5
    save_results("lstm_metrics", {"protocol": "temporal_sequence", "base": a.base,
                                  "split": a.split, "seq_len": lstm.seq_len,
                                  "label_note": "label of last flow in window",
                                  "metrics": metrics})
    print({k: v for k, v in metrics.items() if k in
           ("accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc", "mcc", "fpr", "n_sequences")})


if __name__ == "__main__":
    main()
