"""Probability calibration on VALIDATION data only (never test).

Sigmoid (Platt) calibration for RF attack probabilities. Persisted so
inference applies the identical mapping.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression


class SigmoidCalibrator:
    def __init__(self) -> None:
        self.model = LogisticRegression()
        self._fitted = False

    def fit(self, scores_val: np.ndarray, y_val: np.ndarray) -> "SigmoidCalibrator":
        self.model.fit(np.asarray(scores_val).reshape(-1, 1), np.asarray(y_val))
        self._fitted = True
        return self

    def transform(self, scores: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Calibrator not fitted.")
        return np.asarray(self.model.predict_proba(np.asarray(scores).reshape(-1, 1))[:, 1])

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, p)

    @classmethod
    def load(cls, path: str | Path) -> "SigmoidCalibrator":
        c = cls()
        c.model = joblib.load(path)
        c._fitted = True
        return c
