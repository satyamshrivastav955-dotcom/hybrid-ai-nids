"""Unseen-attack evaluation: known vs held-out attack families reported SEPARATELY.

Usage: python -m evaluation.unseen_attack --splits data/splits --models models
Requires splits built with the unseen_attack protocol (see scripts/prepare_data.py).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.common import benign_index, load_artifacts, model_signals, save_results
from evaluation.metrics import classification_metrics
from ml.preprocessing.cleaning import normalize_labels


def run(splits_dir: Path, model_dir: Path, results_dir: Path, base: str = "cicids2017_unseen") -> dict:
    meta_path = splits_dir / f"{base}_meta.json"
    if not meta_path.exists():
        # fall back to standard base if unseen splits were stored under the default base
        base = "cicids2017"
        meta_path = splits_dir / f"{base}_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    holdout = set(meta.get("holdout_families", []))
    art = load_artifacts(model_dir)
    pre = art["pre"]
    test = pd.read_parquet(splits_dir / f"{base}_test.parquet")
    labels = normalize_labels(test[pre.label_col_])
    X = pre.transform(test)
    sig = model_signals(art, X)
    scores = np.asarray(sig["random_forest"] if art["ens"] is None else np.asarray(art["ens"].fuse(sig)["final_risk_score"]))
    if art["ens"] is not None:
        pred = np.asarray(art["ens"].fuse(sig)["final_prediction"])
    else:
        pred = (scores >= 0.5).astype(int)

    is_benign = labels.str.lower() == "benign"
    is_unseen = labels.isin(holdout)
    is_known_attack = ~(is_benign | is_unseen)

    def subset(mask: pd.Series, name: str) -> dict:
        yt = (~(labels[mask].str.lower() == "benign")).astype(int).values
        yp = pred[np.asarray(mask)]
        ys = scores[np.asarray(mask)]
        m = classification_metrics(yt, yp, ys) if len(yt) else {"n": 0}
        m["n"] = int(np.asarray(mask).sum())
        return m

    payload = {
        "protocol": "unseen_attack",
        "holdout_families": sorted(holdout),
        "known_attack_performance": subset(is_known_attack | is_benign, "known"),
        "unseen_attack_performance": subset(is_unseen | is_benign, "unseen"),
        "warning": "Known and unseen metrics are reported separately and MUST NOT be merged.",
    }
    save_results("unseen_attack_metrics", payload, results_dir)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--base", default="cicids2017_unseen")
    a = ap.parse_args()
    print(json.dumps(run(Path(a.splits), Path(a.models), Path(a.out), a.base), indent=2, default=str))


if __name__ == "__main__":
    main()
