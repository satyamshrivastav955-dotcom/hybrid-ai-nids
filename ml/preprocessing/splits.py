"""Train/validation/test split protocols with leakage guards.

Protocols:
  standard_stratified : stratified shuffle split (seed-controlled).
  temporal            : chronological split on a timestamp column (earlier=train).
  unseen_attack       : configured attack families are held out of train/val entirely
                        and appear ONLY in test (genuine unseen-attack evaluation).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from ml.common import assert_no_leakage
from ml.preprocessing.cleaning import normalize_labels, resolve_label_column, standardize_columns

logger = logging.getLogger(__name__)


@dataclass
class SplitResult:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    metadata: dict


def _row_ids(df: pd.DataFrame) -> set:
    if "_rowid" in df.columns:
        return set(df["_rowid"].astype(str))
    return set(df.index.astype(str)) if not df.empty else set()


def _save_split(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def dataset_fingerprint(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(str(df.shape).encode())
    h.update(",".join(map(str, df.columns)).encode())
    return h.hexdigest()[:12]


def standard_split(
    df: pd.DataFrame,
    label_col: str,
    test_size: float = 0.2,
    val_size: float = 0.15,
    seed: int = 42,
) -> SplitResult:
    df = standardize_columns(df).reset_index(drop=True)
    label_col = resolve_label_column(df, label_col)
    df = df.copy()
    df["_rowid"] = np.arange(len(df))
    y = normalize_labels(df[label_col])
    sss = StratifiedShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
    train_val_idx, test_idx = next(sss.split(df, y))
    train_val, test = df.iloc[train_val_idx], df.iloc[test_idx]
    y_tv = y.iloc[train_val_idx]
    sss2 = StratifiedShuffleSplit(n_splits=1, test_size=val_size, random_state=seed + 1)
    tr_idx, va_idx = next(sss2.split(train_val, y_tv))
    train, val = train_val.iloc[tr_idx].reset_index(drop=True), train_val.iloc[va_idx].reset_index(drop=True)
    test = test.reset_index(drop=True)
    assert_no_leakage(_row_ids(train), _row_ids(val), "standard/val")
    assert_no_leakage(_row_ids(train), _row_ids(test), "standard/test")
    for _d in (train, val, test):
        if "_rowid" in _d.columns:
            _d.drop(columns=["_rowid"], inplace=True)
    meta = {
        "protocol": "standard_stratified",
        "seed": seed,
        "label_column": label_col,
        "class_counts": {
            "train": y.iloc[train_val_idx].iloc[tr_idx].value_counts().to_dict(),
            "val": y.iloc[train_val_idx].iloc[va_idx].value_counts().to_dict(),
            "test": y.iloc[test_idx].value_counts().to_dict(),
        },
    }
    return SplitResult(train, val, test, meta)


def temporal_split(
    df: pd.DataFrame,
    label_col: str,
    timestamp_col: str = "Timestamp",
    test_size: float = 0.2,
    val_size: float = 0.15,
    test_days: int = 0,
) -> SplitResult:
    """Chronological split. test_days>=1: test = last N calendar days (day-aware,
    preferred for network data); otherwise last test_size fraction of rows."""
    df = standardize_columns(df).reset_index(drop=True)
    label_col = resolve_label_column(df, label_col)
    if timestamp_col not in df.columns:
        raise KeyError(f"Timestamp column '{timestamp_col}' missing; cannot do temporal split.")
    # CICIDS2017 day files use inconsistent timestamp formats (zero-padded with
    # seconds vs bare D/M/YYYY). format='mixed' parses element-wise; dayfirst
    # matches the dataset's D/M/YYYY convention (verified July 3..7 monotonic).
    df["_ts"] = pd.to_datetime(df[timestamp_col], errors="coerce", format="mixed", dayfirst=True)
    df = df.sort_values("_ts").reset_index(drop=True)
    n = len(df)
    if test_days and test_days > 0:
        days = pd.Series(df["_ts"].dt.date)
        uniq = sorted(days.dropna().unique())
        test_dates = set(uniq[-test_days:])
        test_mask = days.isin(test_dates).values
        test = df[test_mask].drop(columns=["_ts"]).reset_index(drop=True)
        rest = df[~test_mask].reset_index(drop=True)
        n_val = max(1, int(len(rest) * val_size))
        val = rest.iloc[len(rest) - n_val :].drop(columns=["_ts"]).reset_index(drop=True)
        train = rest.iloc[: len(rest) - n_val].drop(columns=["_ts"]).reset_index(drop=True)
    else:
        n_test = max(1, int(n * test_size))
        n_val = max(1, int((n - n_test) * val_size))
        test = df.iloc[n - n_test :].drop(columns=["_ts"]).reset_index(drop=True)
        val = df.iloc[n - n_test - n_val : n - n_test].drop(columns=["_ts"]).reset_index(drop=True)
        train = df.iloc[: n - n_test - n_val].drop(columns=["_ts"]).reset_index(drop=True)
    y = normalize_labels(df[label_col])
    # Partitions are contiguous in time (sorted ascending): train | val | test.
    meta = {
        "protocol": "temporal",
        "timestamp_column": timestamp_col,
        "test_days": int(test_days),
        "train_time_range": [str(df["_ts"].iloc[0]), str(df["_ts"].iloc[len(train) - 1])] if len(train) else [],
        "test_time_range": [str(df["_ts"].iloc[n - len(test)]), str(df["_ts"].iloc[n - 1])] if len(test) else [],
        "class_counts": {
            "train": normalize_labels(train[label_col]).value_counts().to_dict(),
            "val": normalize_labels(val[label_col]).value_counts().to_dict(),
            "test": normalize_labels(test[label_col]).value_counts().to_dict(),
        },
    }
    logger.info("Temporal split: train=%d val=%d test=%d", len(train), len(val), len(test))
    return SplitResult(train, val, test, meta)


def unseen_attack_split(
    df: pd.DataFrame,
    label_col: str,
    holdout_families: list[str],
    test_size: float = 0.2,
    val_size: float = 0.15,
    seed: int = 42,
) -> SplitResult:
    """Hold out entire attack families from train/val; they appear ONLY in test."""
    df = standardize_columns(df).reset_index(drop=True)
    label_col = resolve_label_column(df, label_col)
    y = normalize_labels(df[label_col])
    hold = {h.strip() for h in holdout_families}
    mask_hold = y.isin(hold)
    if not mask_hold.any():
        raise ValueError(f"Holdout families {holdout_families} not present in labels: {sorted(y.unique())[:20]}")
    df_seen = df[~mask_hold].reset_index(drop=True)
    df_hold = df[mask_hold].reset_index(drop=True)
    seen = standard_split(df_seen, label_col, test_size=test_size, val_size=val_size, seed=seed)
    # Append ALL held-out rows to test only.
    test = pd.concat([seen.test, df_hold], ignore_index=True)
    test = test.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    leaked = set(normalize_labels(seen.train[label_col]).unique()) & hold
    if leaked:
        raise ValueError(f"LEAKAGE: holdout families present in train: {leaked}")
    meta = {
        "protocol": "unseen_attack",
        "seed": seed,
        "holdout_families": sorted(hold),
        "known_attack_test_size": len(seen.test),
        "unseen_test_size": len(df_hold),
        "class_counts": {
            "train": normalize_labels(seen.train[label_col]).value_counts().to_dict(),
            "val": normalize_labels(seen.val[label_col]).value_counts().to_dict(),
            "test": normalize_labels(test[label_col]).value_counts().to_dict(),
        },
    }
    return SplitResult(seen.train, seen.val, test, meta)


def persist_splits(result: SplitResult, splits_dir: str | Path, base: str = "cicids2017") -> dict:
    d = Path(splits_dir)
    d.mkdir(parents=True, exist_ok=True)
    _save_split(result.train, d / f"{base}_train.parquet")
    _save_split(result.val, d / f"{base}_val.parquet")
    _save_split(result.test, d / f"{base}_test.parquet")
    meta = dict(result.metadata)
    meta["paths"] = {
        "train": f"{base}_train.parquet",
        "val": f"{base}_val.parquet",
        "test": f"{base}_test.parquet",
    }
    (d / f"{base}_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return meta
