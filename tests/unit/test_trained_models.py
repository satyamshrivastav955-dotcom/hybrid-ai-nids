"""Unit: trained-model smoke (RF/AE/IF/LSTM) on the session synthetic fixture."""
import json

import numpy as np
import pandas as pd

from evaluation.common import load_artifacts, model_signals
from ml.preprocessing.cleaning import normalize_labels


def test_artifacts_load_and_signal_ranges(synthetic_project):
    art = load_artifacts(synthetic_project["models"])
    assert art["rf"] is not None and art["ae"] is not None and art["if"] is not None
    test = pd.read_parquet(synthetic_project["splits"] / "cicids2017_test.parquet")
    X = art["pre"].transform(test)
    sig = model_signals(art, X)
    assert "random_forest" in sig and "autoencoder" in sig and "isolation_forest" in sig
    for v in sig.values():
        assert np.all((np.asarray(v) >= 0) & (np.asarray(v) <= 1))
    assert art["ens"] is not None
    fused = art["ens"].fuse(sig)
    assert 0.0 <= float(np.asarray(fused["final_risk_score"]).flat[0]) <= 1.0
    # LSTM artifact exists via fallback training
    assert art["lstm"] is not None
