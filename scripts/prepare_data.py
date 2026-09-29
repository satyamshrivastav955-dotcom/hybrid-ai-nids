"""Dataset preparation: raw CSV -> interim -> processed -> splits + manifest.

Usage:
  python scripts/prepare_data.py --raw data/raw --out data --protocol all
  python scripts/prepare_data.py --synthetic --n 300   # DEMO/testing only

Reads configs/data.yaml + configs/features.yaml (split params only).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.common import load_yaml, set_seed  # noqa: E402
from ml.preprocessing.manifest import build_manifest  # noqa: E402
from ml.preprocessing.splits import persist_splits, standard_split, temporal_split, unseen_attack_split  # noqa: E402


def _load_raw(raw_dir: Path) -> pd.DataFrame:
    csvs = sorted(raw_dir.rglob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files under {raw_dir}. Place CICIDS2017 CSVs there or use --synthetic.")
    frames = []
    for f in csvs:
        try:
            frames.append(pd.read_csv(f, low_memory=False))
        except UnicodeDecodeError:
            # Known CICIDS2017 issue: Thursday WebAttacks file contains non-UTF8
            # bytes. latin-1 preserves every byte; modelling only uses numeric
            # columns so this is lossless for our purposes.
            print(f"WARNING: {f.name} is not valid UTF-8; retrying with latin-1.")
            try:
                frames.append(pd.read_csv(f, low_memory=False, encoding="latin-1"))
            except Exception as e:
                print(f"WARNING: skipping {f.name}: {e}")
        except Exception as e:
            print(f"WARNING: skipping {f.name}: {e}")
    if not frames:
        raise FileNotFoundError(f"No readable CSV files under {raw_dir}.")
    df = pd.concat(frames, ignore_index=True)
    print(f"Loaded {len(frames)} CSVs, {len(df)} rows.")
    return df


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data")
    ap.add_argument("--protocol", default="all", choices=["all", "standard_stratified", "temporal", "unseen_attack"])
    ap.add_argument("--synthetic", action="store_true", help="DEMO ONLY: generate synthetic flows.")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    import os
    os.chdir(root)
    cfg = load_yaml("configs/data.yaml")["dataset"]
    set_seed(a.seed)

    out = Path(a.out)
    if a.synthetic:
        from scripts.synthetic_data import generate
        df = generate(n_per_class=a.n, seed=a.seed)
        print(f"SYNTHETIC DEMO DATA: {len(df)} rows. NOT FOR RESEARCH.")
    else:
        df = _load_raw(Path(a.raw))

    (out / "interim").mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / "interim" / "combined.parquet", index=False)

    label_col = cfg.get("label_column", "Label")
    # Drop rows with missing/empty labels (documented; StratifiedShuffleSplit
    # rejects NaN targets and labelless rows are unusable for supervision).
    from ml.preprocessing.cleaning import normalize_labels, resolve_label_column, standardize_columns
    df = standardize_columns(df)
    label_col = resolve_label_column(df, label_col)
    raw_n = len(df)
    lab = normalize_labels(df[label_col].where(df[label_col].notna(), ""))
    keep = lab != ""
    dropped = int((~keep).sum())
    if dropped:
        print(f"Dropped {dropped} rows ({dropped / raw_n:.3%}) with missing labels.")
    df = df[keep].reset_index(drop=True)
    print("Label distribution:")
    print(normalize_labels(df[label_col]).value_counts().to_string())
    protos = [a.protocol] if a.protocol != "all" else ["standard_stratified", "temporal", "unseen_attack"]
    suffix = {"standard_stratified": "cicids2017", "temporal": "cicids2017_temporal",
              "unseen_attack": "cicids2017_unseen"}
    for p in protos:
        try:
            if p == "standard_stratified":
                res = standard_split(df, label_col, cfg.get("test_size", 0.2), cfg.get("val_size", 0.15), a.seed)
            elif p == "temporal":
                tcfg = cfg.get("temporal", {})
                res = temporal_split(df, label_col, cfg.get("timestamp_column", "Timestamp") if "timestamp_column" in cfg else "Timestamp",
                                     test_size=cfg.get("test_size", 0.2), val_size=cfg.get("val_size", 0.15),
                                     test_days=int(tcfg.get("test_days", 0)))
            else:
                res = unseen_attack_split(df, label_col, cfg.get("unseen_attack", {}).get("holdout_families", ["Infiltration"]),
                                          cfg.get("test_size", 0.2), cfg.get("val_size", 0.15), a.seed)
            meta = persist_splits(res, out / "splits", suffix[p])
            print(f"[{p}] train={len(res.train)} val={len(res.val)} test={len(res.test)}")
        except Exception as e:
            print(f"[{p}] skipped: {e}")

    import glob
    splits = [Path(p) for p in glob.glob(str(out / "splits" / "*.parquet"))]
    if splits:
        build_manifest(splits, None, out / "metadata" / "manifest.json",
                       extra={"synthetic": bool(a.synthetic), "seed": a.seed})
        print("Manifest written.")


if __name__ == "__main__":
    main()
