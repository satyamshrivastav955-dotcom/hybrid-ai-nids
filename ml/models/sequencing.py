"""Temporally-ordered sequence builder for the LSTM.

CRITICAL: sequences preserve temporal order. Rows are sorted by timestamp
(and optionally grouped by flow context such as src/dst IP). We NEVER build
sequences from arbitrarily shuffled rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_sequences(
    features: np.ndarray,
    labels: np.ndarray,
    timestamps: pd.Series | np.ndarray | None = None,
    groups: pd.Series | np.ndarray | None = None,
    seq_len: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (X_seq [N, seq_len, F], y_seq [N]) using the label of the LAST flow.

    Ordering: global timestamp sort; if groups given, sequences are formed
    within each group in timestamp order (flows of the same context).
    """
    X = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels)
    n = len(X)
    order = np.arange(n)
    if timestamps is not None:
        ts = pd.to_datetime(pd.Series(timestamps), errors="coerce")
        order = np.argsort(ts.fillna(pd.Timestamp(0)).values, kind="stable")
        X, y = X[order], y[order]
        groups = np.asarray(groups)[order] if groups is not None else None
    seqs, targets = [], []
    if groups is None:
        for i in range(seq_len - 1, n):
            seqs.append(X[i - seq_len + 1 : i + 1])
            targets.append(y[i])
    else:
        g = np.asarray(groups)
        idx_by_group: dict = {}
        for i, key in enumerate(g):
            idx_by_group.setdefault(key, []).append(i)
        for idxs in idx_by_group.values():
            for j in range(seq_len - 1, len(idxs)):
                window = idxs[j - seq_len + 1 : j + 1]
                seqs.append(X[window])
                targets.append(y[idxs[j]])
    if not seqs:
        return np.zeros((0, seq_len, X.shape[1])), np.zeros((0,), dtype=y.dtype if len(y) else float)
    return np.stack(seqs), np.asarray(targets)
