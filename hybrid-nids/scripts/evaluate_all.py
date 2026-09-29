"""Run every evaluation module that has its prerequisites. Saves to experiments/results."""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--out", default="experiments/results")
    ap.add_argument("--figures", default="experiments/figures")
    ap.add_argument("--base", default="cicids2017")
    a = ap.parse_args()
    import os
    os.chdir(Path(__file__).resolve().parents[1])
    from evaluation import ablation, drift, latency, standard, temporal, unseen_attack
    jobs = [
        ("standard", lambda: standard.run(Path(a.splits), Path(a.models), Path(a.out), Path(a.figures), a.base)),
        ("temporal", lambda: temporal.run(Path(a.splits), Path(a.models), Path(a.out), "cicids2017_temporal")),
        ("unseen_attack", lambda: unseen_attack.run(Path(a.splits), Path(a.models), Path(a.out), "cicids2017_unseen")),
        ("drift", lambda: drift.run(Path(a.splits), Path(a.models), Path(a.out), a.base)),
        ("ablation", lambda: ablation.run(Path(a.splits), Path(a.models), Path(a.out), Path(a.figures), a.base)),
        ("latency", lambda: latency.run(Path(a.splits), Path(a.models), Path(a.out), a.base, 500)),
    ]
    for name, fn in jobs:
        try:
            fn()
            print(f"[ok] {name}")
        except Exception as e:
            print(f"[skip] {name}: {e}")
            traceback.print_exc(limit=3)


if __name__ == "__main__":
    main()
