"""Full inference pipeline shared by API, live loop and demo loop.

flow dict -> preprocess (strict schema) -> RF/AE/IF/LSTM signals ->
calibration -> ensemble -> risk -> explainability -> threat intel ->
persistence + alert creation + websocket broadcast payload.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from backend.app.core.config import get_settings
from backend.app.core.logging import new_id
from ml.ensemble.ensemble import EnsembleEngine
from ml.ensemble.risk_engine import RiskEngine
from ml.ensemble.score_normalizer import rf_attack_probability
from ml.explainability.explainer import anomaly_top_features, rf_top_features
from ml.models.autoencoder import AutoencoderModel
from ml.models.isolation_forest import IsolationForestModel
from ml.models.lstm import LSTMModel
from ml.models.random_forest import RandomForestModel
from ml.preprocessing.pipeline import FlowPreprocessor
from ml.threat_intel.providers import get_provider

logger = logging.getLogger(__name__)


class InferenceService:
    def __init__(self, model_dir: str | Path | None = None) -> None:
        self.settings = get_settings()
        self.model_dir = Path(model_dir or self.settings.model_dir)
        self.pre: FlowPreprocessor | None = None
        self.rf: RandomForestModel | None = None
        self.ae: AutoencoderModel | None = None
        self.iff: IsolationForestModel | None = None
        self.lstm: LSTMModel | None = None
        self.ens: EnsembleEngine | None = None
        self.calibrator = None
        self.risk = RiskEngine()
        self.classes: list[str] = []
        self.loaded = False
        # rolling buffer for LSTM sequences (last N feature rows)
        self._seq_buffer: list[np.ndarray] = []
        self._seq_len = 10

    def load(self) -> bool:
        try:
            self.pre = FlowPreprocessor.load(self.model_dir)
            self.rf = RandomForestModel.load(self.model_dir)
            self.classes = list(self.pre.label_encoder_.classes_)
            try:
                self.ae = AutoencoderModel.load(self.model_dir)
            except Exception as e:
                logger.warning("Autoencoder unavailable: %s", e)
            try:
                self.iff = IsolationForestModel.load(self.model_dir)
            except Exception as e:
                logger.warning("IsolationForest unavailable: %s", e)
            try:
                self.lstm = LSTMModel.load(self.model_dir)
                self._seq_len = self.lstm.seq_len
            except Exception as e:
                logger.warning("LSTM unavailable: %s", e)
            ens_path = self.model_dir / "ensemble_config.json"
            if ens_path.exists():
                self.ens = EnsembleEngine.load(ens_path)
            else:
                self.ens = EnsembleEngine()
            cal_path = self.model_dir / "rf_calibrator.joblib"
            if cal_path.exists():
                self.calibrator = joblib.load(cal_path)
            self.loaded = True
            logger.info("Models loaded from %s (classes=%s)", self.model_dir, self.classes)
        except Exception as e:
            logger.error("Model load failed: %s", e)
            self.loaded = False
        return self.loaded

    @property
    def benign_index(self) -> int:
        for i, c in enumerate(self.classes):
            if str(c).strip().lower() == "benign":
                return i
        return 0

    def _signals(self, X: np.ndarray) -> dict[str, np.ndarray]:
        assert self.rf is not None
        model_classes = list(self.rf.model.classes_)
        col = model_classes.index(self.benign_index) if self.benign_index in model_classes else None
        s_rf = rf_attack_probability(self.rf.predict_proba(X), col)
        if self.calibrator is not None:
            try:
                s_rf = np.asarray(self.calibrator.predict_proba(s_rf.reshape(-1, 1))[:, 1])
            except Exception:
                pass
        signals: dict[str, np.ndarray] = {"random_forest": s_rf}
        if self.ae is not None:
            try:
                signals["autoencoder"] = self.ae.anomaly_score(X)
            except Exception:
                signals["autoencoder"] = np.clip(self.ae.reconstruction_error(X), 0, 1)
        if self.iff is not None:
            try:
                signals["isolation_forest"] = self.iff.anomaly_score(X)
            except Exception:
                pass
        if self.lstm is not None and len(self._seq_buffer) >= self._seq_len - 1:
            try:
                seq = np.stack(self._seq_buffer[-(self._seq_len - 1):] + [X[0]])[None, :, :]
                signals["lstm"] = np.array([float(self.lstm.predict_proba(seq)[0])])
            except Exception as e:
                logger.debug("LSTM signal skipped: %s", e)
        return signals

    def predict_one(self, flow: dict[str, Any], source: str = "dataset") -> dict[str, Any]:
        t0 = time.perf_counter()
        request_id = new_id("req")
        if not self.loaded or self.pre is None or self.rf is None or self.ens is None:
            raise RuntimeError("Models not loaded. Train first (scripts/train_all.py).")
        feats = dict(flow.get("features", {}))
        assert self.pre is not None
        missing = [f for f in self.pre.feature_names_ if f not in feats]
        imputed: list[str] = []
        if missing:
            # Graceful degradation for live/demo traffic: impute training medians,
            # log the mismatch and report it — never silently feed wrong layouts.
            for f in missing:
                feats[f] = float(self.pre.medians_.get(f, 0.0))
            imputed = missing
            logger.warning("Schema mismatch request=%s: %d features imputed with training medians: %s",
                           request_id, len(missing), missing[:10])
        row = pd.DataFrame([{**feats, self.pre.label_col_: "BENIGN"}])
        try:
            X = self.pre.transform(row)
        except KeyError as e:
            logger.error("Schema mismatch request=%s: %s", request_id, e)
            raise ValueError(f"Feature schema mismatch: {e}")
        signals = self._signals(X)
        self._seq_buffer.append(X[0])
        if len(self._seq_buffer) > 64:
            self._seq_buffer.pop(0)
        fused = self.ens.fuse(signals)
        risk_val = float(np.asarray(fused["final_risk_score"]).flat[0])
        # predicted attack family from RF multiclass head
        rf_id = int(self.rf.predict(X)[0])
        pred_label = self.classes[rf_id] if 0 <= rf_id < len(self.classes) else "Unknown"
        if risk_val < self.ens.decision_threshold:
            pred_label = "BENIGN"
        elif pred_label.strip().lower() == "benign":
            # Anomaly detectors disagree with the supervised head: flag honestly
            # as an unclassified anomaly, never as a known attack family.
            pred_label = "Anomaly"
        decision = self.risk.decide(pred_label, risk_val,
                                    {k: float(np.asarray(v).flat[0]) for k, v in signals.items()},
                                    confidence=float(np.asarray(fused["confidence"]).flat[0]),
                                    threshold=self.ens.decision_threshold)
        # Explainability (computed, never fabricated)
        top: list[dict] = []
        try:
            top = rf_top_features(self.rf.feature_importance(), self.pre.feature_names_, X[0])
            if self.ae is not None and risk_val >= 0.25:
                ae_top = anomaly_top_features(self.ae.per_feature_error(X)[0], self.pre.feature_names_, top_n=3)
                merged: dict[str, dict] = {t["feature"]: t for t in top}
                for t in ae_top:
                    if t["feature"] in merged:
                        merged[t["feature"]] = {
                            "feature": t["feature"],
                            "contribution": round(max(merged[t["feature"]]["contribution"], t["contribution"]), 4),
                        }
                    else:
                        merged[t["feature"]] = t
                top = sorted(merged.values(), key=lambda t: -t["contribution"])[:5]
        except Exception as e:
            logger.debug("Explainability skipped: %s", e)
        intel = {}
        try:
            src_ip = flow.get("src_ip", "")
            if src_ip:
                intel = get_provider().lookup(src_ip).to_dict()
        except Exception as e:
            logger.debug("Threat intel skipped: %s", e)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        from backend.app.services.alerts import _display
        return {
            "request_id": request_id,
            "prediction": _display(decision["prediction"]),
            "risk_score": decision["risk_score"],
            "severity": decision["severity"],
            "confidence": decision["confidence"],
            "signals": decision["signals"],
            "explanation": self.ens.explanation(fused),
            "top_features": top,
            "threat_intel": intel,
            "source": source,
            "latency_ms": round(latency_ms, 3),
            "imputed_features": imputed,
            "model_versions": {"random_forest": "v1.0.0", "ensemble": self.ens.mode},
        }

    def status(self) -> dict:
        return {"loaded": self.loaded, "classes": self.classes,
                "models": {"rf": self.rf is not None, "ae": self.ae is not None,
                           "if": self.iff is not None, "lstm": self.lstm is not None,
                           "ensemble": self.ens.mode if self.ens else None}}
