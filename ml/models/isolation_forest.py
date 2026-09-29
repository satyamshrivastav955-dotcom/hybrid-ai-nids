"""Isolation Forest anomaly detector (benign-only training).

Raw decision_function outputs are mapped to a stable 0..1 anomaly score via
min-max statistics learned on benign VALIDATION data (never test).
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from ml.common import git_commit


class IsolationForestModel:
    name = "isolation_forest"

    def __init__(self, n_estimators: int = 200, max_samples: str | float = "auto",
                 contamination: str | float = "auto", random_state: int = 42) -> None:
        self.params = {
            "n_estimators": int(n_estimators),
            "max_samples": max_samples,
            "contamination": contamination,
            "random_state": int(random_state),
        }
        self.model = IsolationForest(
            n_estimators=self.params["n_estimators"],
            max_samples=self.params["max_samples"],
            contamination=self.params["contamination"],
            random_state=self.params["random_state"],
        )
        self._lo: float | None = None  # min decision score on benign val
        self._hi: float | None = None  # max decision score on benign val

    def fit(self, X_benign_train: np.ndarray) -> "IsolationForestModel":
        self.model.fit(X_benign_train)
        return self

    def calibrate(self, X_benign_val: np.ndarray) -> None:
        s = self.model.decision_function(X_benign_val).astype(float)
        self._lo, self._hi = float(s.min()), float(s.max())
        if self._hi - self._lo < 1e-9:
            self._hi = self._lo + 1e-9

    def raw_score(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.decision_function(X), dtype=np.float64)

    def anomaly_score(self, X: np.ndarray) -> np.ndarray:
        """0..1 where 1 = most anomalous (lower decision_function => higher score)."""
        if self._lo is None or self._hi is None:
            raise RuntimeError("Not calibrated. Call calibrate on benign validation first.")
        s = self.raw_score(X)
        norm = (s - self._lo) / (self._hi - self._lo)
        return np.clip(1.0 - norm, 0.0, 1.0)

    def save(self, model_dir: str | Path, extra: dict | None = None) -> None:
        d = Path(model_dir)
        d.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, d / "isolation_forest.joblib")
        meta = {
            "model_name": self.name, "version": "v1.0.0", "params": self.params,
            "calibration": {"lo": self._lo, "hi": self._hi},
            "git_commit": git_commit(), **(extra or {}),
        }
        (d / "isolation_forest_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, model_dir: str | Path) -> "IsolationForestModel":
        d = Path(model_dir)
        meta = json.loads((d / "isolation_forest_meta.json").read_text(encoding="utf-8"))
        p = meta.get("params", {})
        obj = cls(n_estimators=p.get("n_estimators", 200),
                  max_samples=p.get("max_samples", "auto"),
                  contamination=p.get("contamination", "auto"),
                  random_state=p.get("random_state", 42))
        obj.model = joblib.load(d / "isolation_forest.joblib")
        cal = meta.get("calibration", {})
        obj._lo, obj._hi = cal.get("lo"), cal.get("hi")
        return obj
