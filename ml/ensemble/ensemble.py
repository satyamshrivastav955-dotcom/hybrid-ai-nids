"""Adaptive decision-level ensemble.

final_risk = w_rf*s_rf + w_ae*s_ae + w_if*s_if + w_lstm*s_lstm,  sum(w)=1, w>=0.

Modes:
  manual               : weights from configs/ensemble.yaml.
  validation_optimized : coarse grid search on VALIDATION signals maximising a
                         chosen metric (never test data).
"""
from __future__ import annotations

import itertools
import json
import logging
from pathlib import Path

import numpy as np

from ml.ensemble.score_normalizer import MODEL_KEYS, validate_signals

logger = logging.getLogger(__name__)


class EnsembleEngine:
    def __init__(self, weights: dict[str, float] | None = None,
                 decision_threshold: float = 0.5, mode: str = "manual") -> None:
        self.weights = dict(weights) if weights else {k: 1.0 / len(MODEL_KEYS) for k in MODEL_KEYS}
        self._normalise_weights()
        self.decision_threshold = float(decision_threshold)
        self.mode = mode
        self.metric_: str | None = None
        self.val_score_: float | None = None

    def _normalise_weights(self) -> None:
        total = sum(max(0.0, float(self.weights.get(k, 0.0))) for k in MODEL_KEYS)
        if total <= 0:
            raise ValueError("Ensemble weights must sum to a positive value.")
        for k in MODEL_KEYS:
            self.weights[k] = max(0.0, float(self.weights.get(k, 0.0))) / total

    def fuse(self, signals: dict) -> dict:
        s = validate_signals(signals)
        # Align lengths; scalars broadcast.
        n = max(np.asarray(v).size for v in s.values())
        acc = np.zeros(n)
        wsum = 0.0
        contributing = {}
        for k, v in s.items():
            arr = np.full(n, float(v)) if np.asarray(v).size == 1 else np.asarray(v, dtype=float)
            w = float(self.weights.get(k, 0.0))
            acc += w * arr
            wsum += w
            contributing[k] = round(float(np.mean(arr)), 4)
        risk = acc / max(wsum, 1e-9)
        pred = (risk >= self.decision_threshold).astype(int)
        confidence = np.abs(risk - 0.5) * 2.0
        if n == 1:
            return {"final_risk_score": float(risk[0]), "final_prediction": int(pred[0]),
                    "confidence": float(confidence[0]), "contributing_models": contributing,
                    "weights": dict(self.weights)}
        return {"final_risk_score": risk, "final_prediction": pred, "confidence": confidence,
                "contributing_models": contributing, "weights": dict(self.weights)}

    def optimize_weights(self, signals_val: dict, y_val: np.ndarray,
                         metric: str = "f1", step: float = 0.1) -> dict:
        from sklearn.metrics import f1_score, roc_auc_score
        s = validate_signals(signals_val)
        keys = list(s.keys())
        y = np.asarray(y_val)
        grid = np.arange(0.0, 1.0 + 1e-9, step)
        best, best_w, best_m = -1.0, None, None
        for combo in itertools.product(grid, repeat=len(keys)):
            if sum(combo) <= 0:
                continue
            w = {k: c / sum(combo) for k, c in zip(keys, combo)}
            acc = sum(w[k] * np.asarray(s[k], dtype=float) for k in keys)
            pred = (acc >= self.decision_threshold).astype(int)
            try:
                m = float(roc_auc_score(y, acc)) if metric == "roc_auc" else float(f1_score(y, pred, zero_division=0))
            except ValueError:
                continue
            if m > best:
                best, best_w, best_m = m, w, metric
        if best_w is None:
            raise RuntimeError("Weight optimisation failed on validation signals.")
        full = {k: float(best_w.get(k, 0.0)) for k in MODEL_KEYS}
        self.weights = full
        self.mode = "validation_optimized"
        self.metric_, self.val_score_ = metric, best
        logger.info("Optimised ensemble weights on validation (%s=%.4f): %s", metric, best, full)
        return {"weights": full, "metric": metric, "score": best}

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"weights": self.weights, "mode": self.mode,
                                 "decision_threshold": self.decision_threshold,
                                 "metric": self.metric_, "val_score": self.val_score_}, indent=2),
                     encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "EnsembleEngine":
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        obj = cls(weights=cfg.get("weights"), decision_threshold=cfg.get("decision_threshold", 0.5),
                  mode=cfg.get("mode", "manual"))
        obj.metric_, obj.val_score_ = cfg.get("metric"), cfg.get("val_score")
        return obj

    def explanation(self, fused: dict) -> str:
        parts = ", ".join(f"{k}={v:.2f}" for k, v in fused.get("contributing_models", {}).items())
        n_high = sum(1 for v in fused.get("contributing_models", {}).values() if v >= 0.5)
        verdict = ("multiple detection mechanisms independently identified anomalous activity"
                   if n_high >= 2 else "a detection mechanism identified potentially anomalous activity")
        return (f"Final risk score {fused.get('final_risk_score', 0):.2f} ({parts}). "
                f"Flagged because {verdict}. Review contributing features and threat context.")
