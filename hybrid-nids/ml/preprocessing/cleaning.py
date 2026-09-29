"""Column standardisation + basic cleaning for CICIDS2017-style flow CSVs.

All *learned* statistics (medians, variances, correlations, scaler params)
are fitted on TRAINING data only by FlowPreprocessor. The functions here are
stateless row-wise cleaning steps that are safe to apply anywhere.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LABEL_CANDIDATES = ["Label", " Label", "label", "class", "Class"]
BENIGN_TOKENS = {"benign"}


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def resolve_label_column(df: pd.DataFrame, configured: str | None = None) -> str:
    if configured and configured in df.columns:
        return configured
    for cand in LABEL_CANDIDATES:
        if cand in df.columns:
            return cand
    raise KeyError(f"No label column found. Columns: {list(df.columns)[:10]}...")


def normalize_labels(series: pd.Series) -> pd.Series:
    """Strip whitespace; keep original attack names verbatim otherwise."""
    return series.astype(str).str.strip()


def is_benign(label: str, benign_label: str = "BENIGN") -> bool:
    return str(label).strip().lower() == benign_label.strip().lower()


def replace_inf_with_nan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    num = df.select_dtypes(include=[np.number]).columns
    df[num] = df[num].replace([np.inf, -np.inf], np.nan)
    return df


def coerce_numeric(df: pd.DataFrame, exclude: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if col in exclude:
            continue
        if df[col].dtype == object:
            coerced = pd.to_numeric(df[col], errors="coerce")
            # Keep the column numeric only if at least half the values parse.
            if coerced.notna().mean() >= 0.5:
                df[col] = coerced
    return df


def basic_clean(df: pd.DataFrame, label_col: str, drop_cols: list[str]) -> pd.DataFrame:
    """Stateless cleaning: standardise, drop identifiers, inf->NaN, coerce numerics."""
    df = standardize_columns(df)
    if label_col not in df.columns:
        label_col = resolve_label_column(df, label_col)
    drop = [c for c in drop_cols if c in df.columns and c != label_col]
    df = df.drop(columns=drop)
    df = replace_inf_with_nan(df)
    df = coerce_numeric(df, exclude=[label_col])
    return df
