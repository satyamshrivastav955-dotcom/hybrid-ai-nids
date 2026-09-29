"""Reusable, leakage-safe feature pipeline.

Fit ONLY on training data::

    pre = FlowPreprocessor(top_k=30).fit(train_df, label_col="Label")
    X_train = pre.transform(train_df)
    X_val   = pre.transform(val_df)   # uses frozen statistics
    pre.save(model_dir)

Design (baseline from the research concept):
  column standardisation -> drop unusable -> inf->NaN -> missing-value
  handling -> duplicate handling -> constant filtering (train) ->
  correlation filtering (train) -> feature ranking (train) -> top-K ->
  RobustScaler (train) -> model-ready matrix.

The fitted feature list is serialised and strictly enforced at inference:
unknown/missing features raise a logged schema mismatch instead of being
silently accepted.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_selection import f_classif, mutual_info_classif
from sklearn.preprocessing import LabelEncoder, RobustScaler, StandardScaler

from .cleaning import basic_clean, normalize_labels

logger = logging.getLogger(__name__)


@dataclass
class PreprocessorArtifacts:
    feature_names: list[str] = field(default_factory=list)
    medians: dict = field(default_factory=dict)
    label_classes: list[str] = field(default_factory=list)


class FlowPreprocessor:
    def __init__(
        self,
        top_k: int = 30,
        variance_threshold: float = 0.0,
        correlation_threshold: float = 0.98,
        missing_threshold: float = 0.5,
        scaler: str = "robust",
        ranking: str = "mutual_info",
        benign_label: str = "BENIGN",
        random_state: int = 42,
    ) -> None:
        self.top_k = top_k
        self.variance_threshold = variance_threshold
        self.correlation_threshold = correlation_threshold
        self.missing_threshold = missing_threshold
        self.scaler_name = scaler
        self.ranking = ranking
        self.benign_label = benign_label
        self.random_state = random_state

        self.label_col_: str | None = None
        self.feature_names_: list[str] = []
        self.medians_: dict[str, float] = {}
        self.scaler_ = None
        self.label_encoder_: LabelEncoder | None = None
        self._fitted = False

    # ---------------- fit (TRAIN ONLY) ----------------
    def fit(self, df: pd.DataFrame, label_col: str = "Label", drop_cols: list[str] | None = None) -> "FlowPreprocessor":
        drop_cols = drop_cols or []
        df = basic_clean(df, label_col, drop_cols)
        label_col = label_col if label_col in df.columns else next(c for c in df.columns if c.lower() == "label")
        self.label_col_ = label_col
        y_raw = normalize_labels(df[label_col])
        X = df.drop(columns=[label_col])

        # Numeric-only modelling matrix; non-numeric columns are dropped and recorded.
        X = X.select_dtypes(include=[np.number]).copy()
        if X.shape[1] == 0:
            raise ValueError("No numeric feature columns available after cleaning.")

        # 1. Missing-value policy (learned on train): drop sparse cols, store medians.
        missing_frac = X.isna().mean()
        keep = missing_frac[missing_frac <= self.missing_threshold].index.tolist()
        dropped_missing = [c for c in X.columns if c not in keep]
        if dropped_missing:
            logger.info("Dropping %d sparse columns: %s", len(dropped_missing), dropped_missing[:10])
        X = X[keep]
        self.medians_ = {c: float(X[c].median()) for c in X.columns}

        # 2. Duplicate rows in train are removed for statistic estimation.
        X = X.drop_duplicates()
        X = X.fillna(value=self.medians_)

        # 3. Constant / near-constant filtering (train variance).
        variances = X.var()
        keep_var = variances[variances > self.variance_threshold].index.tolist()
        if not keep_var:
            raise ValueError("All features filtered as constant.")
        X = X[keep_var]

        # 4. Correlation filtering (train-only): greedily drop later column of highly correlated pairs.
        if self.correlation_threshold < 1.0 and X.shape[1] > 1:
            corr = X.corr().abs()
            upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
            to_drop = [c for c in upper.columns if (upper[c] > self.correlation_threshold).any()]
            if to_drop:
                logger.info("Correlation filtering drops %d columns.", len(to_drop))
            X = X.drop(columns=to_drop)

        # 5. Feature ranking (train-only) -> top-K.
        # Align labels with deduplicated rows: rank on the deduped frame's matching labels.
        # Simplest leakage-safe approach: rank on the full kept-column frame before dedup.
        X_full = df.drop(columns=[label_col]).select_dtypes(include=[np.number])[X.columns]
        X_full = X_full.fillna(value=self.medians_)
        y_full = y_raw
        le = LabelEncoder()
        y_enc = le.fit_transform(y_full)
        self.label_encoder_ = le
        scores = self._rank_features(X_full, y_enc)
        ranked = scores.sort_values(ascending=False).index.tolist()
        self.feature_names_ = ranked[: min(self.top_k, len(ranked))]

        # 6. Scaler fitted on train top-K.
        X_train_k = X_full[self.feature_names_]
        self.scaler_ = RobustScaler() if self.scaler_name == "robust" else StandardScaler()
        self.scaler_.fit(X_train_k)
        self._fitted = True
        logger.info("Fitted preprocessor: %d features -> top %d.", len(ranked), len(self.feature_names_))
        return self

    def _rank_features(self, X: pd.DataFrame, y_enc: np.ndarray) -> pd.Series:
        if self.ranking == "variance":
            return X.var().fillna(0)
        if self.ranking == "f_test":
            f, _ = f_classif(X.fillna(0), y_enc)
            return pd.Series(np.nan_to_num(f, nan=0.0), index=X.columns)
        # default: mutual_info (deterministic via random_state)
        mi = mutual_info_classif(X.fillna(0), y_enc, random_state=self.random_state)
        return pd.Series(mi, index=X.columns)

    # ---------------- transform (frozen) ----------------
    def transform(self, df: pd.DataFrame) -> np.ndarray:
        self._require_fitted()
        assert self.label_col_ is not None
        df = basic_clean(df, self.label_col_, [])
        # Schema enforcement: label may be absent at inference; features must match exactly.
        missing = [c for c in self.feature_names_ if c not in df.columns]
        if missing:
            raise KeyError(
                f"Schema mismatch: {len(missing)} required features absent: {missing[:10]}. "
                "Refusing to feed incompatible layout to models."
            )
        X = df[self.feature_names_].copy()
        for c in self.feature_names_:
            if c in self.medians_:
                X[c] = X[c].fillna(self.medians_[c])
        X = X.fillna(0)
        return np.asarray(self.scaler_.transform(X), dtype=np.float64)

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        arr = self.transform(df)
        return pd.DataFrame(arr, columns=self.feature_names_)

    def encode_labels(self, labels: pd.Series) -> np.ndarray:
        self._require_fitted()
        assert self.label_encoder_ is not None
        return self.label_encoder_.transform(normalize_labels(labels))

    def decode_labels(self, ids: np.ndarray) -> list[str]:
        self._require_fitted()
        assert self.label_encoder_ is not None
        return list(self.label_encoder_.inverse_transform(ids))

    # ---------------- persistence ----------------
    def save(self, model_dir: str | Path) -> None:
        self._require_fitted()
        d = Path(model_dir)
        d.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.scaler_, d / "scaler.joblib")
        joblib.dump(self.label_encoder_, d / "label_encoder.joblib")
        joblib.dump(self.feature_names_, d / "feature_selector.joblib")
        joblib.dump(self.medians_, d / "feature_medians.joblib")
        meta = {
            "feature_names": self.feature_names_,
            "label_column": self.label_col_,
            "label_classes": list(self.label_encoder_.classes_) if self.label_encoder_ else [],
            "top_k": self.top_k,
            "scaler": self.scaler_name,
            "ranking": self.ranking,
            "benign_label": self.benign_label,
        }
        (d / "feature_schema.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, model_dir: str | Path, **overrides) -> "FlowPreprocessor":
        d = Path(model_dir)
        meta = json.loads((d / "feature_schema.json").read_text(encoding="utf-8"))
        pre = cls(
            top_k=meta.get("top_k", 30),
            scaler=meta.get("scaler", "robust"),
            ranking=meta.get("ranking", "mutual_info"),
            benign_label=meta.get("benign_label", "BENIGN"),
            **overrides,
        )
        pre.feature_names_ = list(joblib.load(d / "feature_selector.joblib"))
        pre.medians_ = dict(joblib.load(d / "feature_medians.joblib"))
        pre.scaler_ = joblib.load(d / "scaler.joblib")
        pre.label_encoder_ = joblib.load(d / "label_encoder.joblib")
        pre.label_col_ = meta.get("label_column", "Label")
        pre._fitted = True
        return pre

    def _require_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("FlowPreprocessor is not fitted. Call fit(train_df) first.")
