"""Unit: ensemble fusion, calibration, risk bands, PSI, intel, explainability, sequencing."""
import numpy as np
import pandas as pd

from ml.calibration.calibrator import SigmoidCalibrator
from ml.drift.psi import compute_drift
from ml.ensemble.ensemble import EnsembleEngine
from ml.ensemble.risk_engine import RiskEngine
from ml.ensemble.score_normalizer import rf_attack_probability
from ml.explainability.explainer import anomaly_top_features, rf_top_features
from ml.models.sequencing import build_sequences
from ml.threat_intel.providers import MockProvider, get_provider


def test_rf_attack_probability():
    p = np.array([[0.8, 0.1, 0.1], [0.2, 0.7, 0.1]])
    out = rf_attack_probability(p, 0)
    assert np.allclose(out, [0.2, 0.8])


def test_ensemble_weights_constrained_and_fuse():
    eng = EnsembleEngine(weights={"random_forest": 2, "autoencoder": 1, "isolation_forest": 1, "lstm": 0},
                         decision_threshold=0.5)
    assert abs(sum(eng.weights.values()) - 1.0) < 1e-9
    fused = eng.fuse({"random_forest": np.array([0.9]), "autoencoder": np.array([0.8])})
    assert 0.0 <= fused["final_risk_score"] <= 1.0
    assert fused["final_prediction"] == 1
    assert "Flagged because" in eng.explanation(fused)


def test_ensemble_optimizes_on_validation_only():
    rng = np.random.default_rng(0)
    y = (rng.random(200) > 0.5).astype(int)
    sig = {"random_forest": np.clip(y * 0.7 + rng.random(200) * 0.3, 0, 1),
           "autoencoder": rng.random(200)}
    eng = EnsembleEngine()
    res = eng.optimize_weights(sig, y, metric="f1")
    assert abs(sum(res["weights"].values()) - 1.0) < 1e-9
    assert res["score"] >= 0


def test_calibrator_monotonic():
    s = np.linspace(0, 1, 100)
    y = (s > 0.5).astype(int)
    cal = SigmoidCalibrator().fit(s, y)
    out = cal.transform(np.array([0.1, 0.9]))
    assert out[0] < out[1]


def test_risk_bands():
    r = RiskEngine(low=0.25, medium=0.5, high=0.75)
    assert r.severity(0.1) == "LOW" and r.severity(0.3) == "MEDIUM"
    assert r.severity(0.6) == "HIGH" and r.severity(0.9) == "CRITICAL"
    d = r.decide("DoS", 0.9, {"random_forest": 0.9})
    assert d["severity"] == "CRITICAL" and d["prediction"] == "DoS"


def test_psi_stable_vs_shifted():
    rng = np.random.default_rng(0)
    ref = pd.DataFrame({"a": rng.normal(0, 1, 2000), "b": rng.normal(5, 1, 2000)})
    same = pd.DataFrame({"a": rng.normal(0, 1, 2000), "b": rng.normal(5, 1, 2000)})
    shifted = pd.DataFrame({"a": rng.normal(3, 1, 2000), "b": rng.normal(5, 1, 2000)})
    r1 = compute_drift(ref, same)
    r2 = compute_drift(ref, shifted)
    assert r1["status"] == "STABLE"
    assert r2["status"] in ("MODERATE", "SEVERE")
    assert r2["aggregate_psi"] > r1["aggregate_psi"]
    assert r2["adaptation"]["threshold_changed"] is False  # PSI never auto-mutates thresholds


def test_threat_intel_mock():
    p = get_provider("mock")
    assert isinstance(p, MockProvider)
    r = p.lookup("10.0.0.5")
    assert r.reputation == "benign"  # private
    r2 = p.lookup("8.8.8.8")
    assert r2.provider == "mock" and 0 <= r2.confidence <= 1


def test_explainability_shapes():
    imp = np.array([0.5, 0.3, 0.2])
    top = rf_top_features(imp, ["a", "b", "c"], np.array([2.0, 0.1, 0.1]), top_n=2)
    assert top[0]["feature"] == "a"
    ae = anomaly_top_features(np.array([0.1, 0.9, 0.2]), ["a", "b", "c"], top_n=1)
    assert ae[0]["feature"] == "b"


def test_sequencing_preserves_order():
    X = np.arange(20).reshape(10, 2).astype(float)
    y = np.arange(10)
    ts = pd.Series(pd.date_range("2020-01-01", periods=10, freq="min")[::-1])  # reversed
    Xs, ys = build_sequences(X, y, timestamps=ts, seq_len=3)
    assert Xs.shape == (8, 3, 2)
    # reversed timestamps sort to rows 9..0; first window is [9,8,7] -> target 7
    assert list(ys[:3]) == [7, 6, 5]
    assert list(Xs[0, :, 0]) == [18.0, 16.0, 14.0]
