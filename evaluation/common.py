"""Experiment harness: seeds, artifact loading, result persistence."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.common import git_commit, set_seed
from ml.ensemble.ensemble import EnsembleEngine
from ml.ensemble.score_normalizer import rf_attack_probability
from ml.models.autoencoder import AutoencoderModel
from ml.models.isolation_forest import IsolationForestModel
from ml.models.lstm import LSTMModel
from ml.models.random_forest import RandomForestModel
from ml.models.sequencing import build_sequences
from ml.preprocessing.pipeline import FlowPreprocessor


def load_artifacts(model_dir: Path) -> dict:
    model_dir = Path(model_dir)
    pre = FlowPreprocessor.load(model_dir)
    rf = RandomForestModel.load(model_dir)
    ae, iff, lstm, ens = None, None, None, None
    try:
        ae = AutoencoderModel.load(model_dir)
    except Exception:
        pass
    try:
        iff = IsolationForestModel.load(model_dir)
    except Exception:
        pass
    try:
        lstm = LSTMModel.load(model_dir)
    except Exception:
        pass
    ens_path = model_dir / "ensemble_config.json"
    if ens_path.exists():
        ens = EnsembleEngine.load(ens_path)
    return {"pre": pre, "rf": rf, "ae": ae, "if": iff, "lstm": lstm, "ens": ens,
            "label_classes": list(pre.label_encoder_.classes_)}


def benign_index(label_classes: list[str], benign_label: str = "BENIGN") -> int:
    for i, c in enumerate(label_classes):
        if str(c).strip().lower() == benign_label.strip().lower():
            return i
    raise ValueError(f"Benign label '{benign_label}' not in classes {label_classes}.")


def model_signals(art: dict, X: np.ndarray, X_seq_last: np.ndarray | None = None) -> dict:
    pre, rf = art["pre"], art["rf"]
    bi = benign_index(art["label_classes"])
    # map label position -> column position in predict_proba
    model_classes = list(rf.model.classes_)
    col = model_classes.index(bi) if bi in model_classes else None
    sig = {"random_forest": rf_attack_probability(rf.predict_proba(X), col)}
    if art["ae"] is not None:
        try:
            sig["autoencoder"] = art["ae"].anomaly_score(X)
        except Exception:
            sig["autoencoder"] = np.clip(art["ae"].reconstruction_error(X), 0, 1)
    if art["if"] is not None:
        try:
            sig["isolation_forest"] = art["if"].anomaly_score(X)
        except Exception:
            pass
    # LSTM needs sequences; caller may supply aligned per-row last-flow scores or skip.
    return sig


def save_results(name: str, payload: dict, results_dir: Path = Path("experiments/results")) -> Path:
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    payload = {"experiment": name, "created_at": datetime.datetime.utcnow().isoformat() + "Z",
               "git_commit": git_commit(), **payload}
    path = results_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
