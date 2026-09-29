"""Random Forest: primary supervised known-attack classifier."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from ml.common import git_commit


class RandomForestModel:
    name = "random_forest"

    def __init__(self, **params) -> None:
        self.params = {
            "n_estimators": int(params.get("n_estimators", 200)),
            "max_depth": params.get("max_depth"),
            "min_samples_split": int(params.get("min_samples_split", 2)),
            "min_samples_leaf": int(params.get("min_samples_leaf", 1)),
            "class_weight": params.get("class_weight", "balanced_subsample"),
            "n_jobs": int(params.get("n_jobs", -1)),
            "random_state": int(params.get("random_state", 42)),
        }
        self.model = RandomForestClassifier(**self.params)
        self.classes_: list[str] | None = None
        self.metadata_: dict = {}

    def fit(self, X: np.ndarray, y: np.ndarray, classes: list[str] | None = None) -> "RandomForestModel":
        self.model.fit(X, y)
        n = len(getattr(self.model, "classes_", []))
        self.classes_ = list(classes) if classes else [str(c) for c in range(n)]
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict_proba(X), dtype=np.float64)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.predict(X))

    def benign_index(self, benign_label: str, label_classes: list[str]) -> int | None:
        for i, c in enumerate(label_classes):
            if str(c).strip().lower() == benign_label.strip().lower():
                # map position in label_classes to position in model.classes_ if possible
                try:
                    return list(self.model.classes_).index(i) if i in list(self.model.classes_) else None
                except ValueError:
                    return None
        return None

    def feature_importance(self) -> np.ndarray:
        return np.asarray(self.model.feature_importances_, dtype=np.float64)

    def save(self, model_dir: str | Path, extra: dict | None = None) -> Path:
        d = Path(model_dir)
        d.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, d / "random_forest.joblib")
        meta = {
            "model_name": self.name,
            "version": "v1.0.0",
            "params": self.params,
            "git_commit": git_commit(),
            **(extra or {}),
        }
        (d / "random_forest_meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        self.metadata_ = meta
        return d / "random_forest.joblib"

    @classmethod
    def load(cls, model_dir: str | Path) -> "RandomForestModel":
        d = Path(model_dir)
        obj = cls()
        obj.model = joblib.load(d / "random_forest.joblib")
        return obj
