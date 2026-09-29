"""Latency benchmark: mean/median/p95/p99 + throughput. Measured, never assumed.

Usage: python -m evaluation.latency --splits data/splits --models models --n 500
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from evaluation.common import load_artifacts, model_signals, save_results


def _bench(fn, reps: int = 3) -> dict:
    fn()  # warmup
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000.0)
    a = np.array(ts)
    return {"mean_ms": round(float(a.mean()), 4), "median_ms": round(float(np.median(a)), 4),
            "p95_ms": round(float(np.percentile(a, 95)), 4), "p99_ms": round(float(np.percentile(a, 99)), 4),
            "reps": reps}


def run(splits_dir: Path, model_dir: Path, results_dir: Path, base: str, n: int) -> dict:
    art = load_artifacts(model_dir)
    pre = art["pre"]
    test = pd.read_parquet(splits_dir / f"{base}_test.parquet").head(n)
    raw = test
    out = {}
    X_box: dict = {}
    out["preprocessing"] = _bench(lambda: X_box.setdefault("X", pre.transform(raw)))
    X = X_box["X"]
    out["random_forest"] = _bench(lambda: art["rf"].predict_proba(X))
    if art["ae"] is not None:
        out["autoencoder"] = _bench(lambda: art["ae"].reconstruction_error(X))
    if art["if"] is not None:
        out["isolation_forest"] = _bench(lambda: art["if"].raw_score(X))
    sig = model_signals(art, X)
    if art["ens"] is not None:
        out["ensemble"] = _bench(lambda: art["ens"].fuse(sig))

    def total():
        _X = pre.transform(raw)
        _s = model_signals(art, _X)
        if art["ens"] is not None:
            art["ens"].fuse(_s)
    tot = _bench(total)
    # throughput: rows/sec from mean total latency
    tot["throughput_rows_per_sec"] = round(1000.0 / max(tot["mean_ms"], 1e-9) * len(test), 2)
    tot["batch_rows"] = int(len(test))
    out["total_inference"] = tot
    payload = {"protocol": "latency", "n_rows": int(len(test)), "stages": out,
               "note": "Measured on this machine; sub-millisecond claims require these numbers to show it."}
    save_results("latency_metrics", payload, results_dir)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--base", default="cicids2017")
    ap.add_argument("--n", type=int, default=500)
    a = ap.parse_args()
    print(json.dumps(run(Path(a.splits), Path(a.models), Path(a.out), a.base, a.n), indent=2))


if __name__ == "__main__":
    main()
