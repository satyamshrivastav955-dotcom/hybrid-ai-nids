"""Train all four models + preprocessor + ensemble. Leakage-safe by construction.

Order: fit preprocessor on TRAIN -> transform all splits -> train models ->
thresholds/calibration/weights on VALIDATION -> persist + registry.

Usage: python scripts/train_all.py --splits data/splits --models models [--base cicids2017]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.calibration.calibrator import SigmoidCalibrator  # noqa: E402
from ml.common import git_commit, load_yaml, set_seed  # noqa: E402
from ml.ensemble.ensemble import EnsembleEngine  # noqa: E402
from ml.ensemble.score_normalizer import rf_attack_probability  # noqa: E402
from ml.models.autoencoder import AutoencoderModel  # noqa: E402
from ml.models.isolation_forest import IsolationForestModel  # noqa: E402
from ml.models.lstm import LSTMModel  # noqa: E402
from ml.models.random_forest import RandomForestModel  # noqa: E402
from ml.models.sequencing import build_sequences  # noqa: E402
from ml.preprocessing.cleaning import is_benign, normalize_labels  # noqa: E402
from ml.preprocessing.pipeline import FlowPreprocessor  # noqa: E402
from ml.registry.registry import register_model  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--models", default="models")
    ap.add_argument("--base", default="cicids2017")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fast", action="store_true", help="smaller RF/AE/LSTM for smoke runs")
    a = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    import os
    os.chdir(root)
    set_seed(a.seed)
    t0 = time.time()

    data_cfg = load_yaml("configs/data.yaml")["dataset"]
    feat_cfg = load_yaml("configs/features.yaml")["features"]
    model_cfg = load_yaml("configs/models.yaml")
    ens_cfg = load_yaml("configs/ensemble.yaml")["ensemble"]
    model_dir = Path(a.models)
    model_dir.mkdir(parents=True, exist_ok=True)

    label_col = data_cfg.get("label_column", "Label")
    benign_label = feat_cfg.get("benign_label", "BENIGN")
    train = pd.read_parquet(Path(a.splits) / f"{a.base}_train.parquet")
    val = pd.read_parquet(Path(a.splits) / f"{a.base}_val.parquet")
    print(f"train={len(train)} val={len(val)}")

    # 1. Preprocessor fitted on TRAIN ONLY.
    pre = FlowPreprocessor(top_k=feat_cfg.get("top_k", 30),
                           variance_threshold=feat_cfg.get("variance_threshold", 0.0),
                           correlation_threshold=feat_cfg.get("correlation_threshold", 0.98),
                           missing_threshold=feat_cfg.get("missing_threshold", 0.5),
                           scaler=feat_cfg.get("scaler", "robust"),
                           ranking=feat_cfg.get("ranking", "mutual_info"),
                           benign_label=benign_label, random_state=a.seed)
    drop_cols = data_cfg.get("drop_columns", [])
    pre.fit(train, label_col=label_col, drop_cols=drop_cols)
    label_col = pre.label_col_
    X_train, X_val = pre.transform(train), pre.transform(val)
    y_train = pre.encode_labels(train[label_col])
    y_val = pre.encode_labels(val[label_col])
    classes = list(pre.label_encoder_.classes_)
    bi = next(i for i, c in enumerate(classes) if str(c).strip().lower() == benign_label.strip().lower())
    yb_train, yb_val = (y_train != bi).astype(int), (y_val != bi).astype(int)
    pre.save(model_dir)
    print(f"Features ({len(pre.feature_names_)}): {pre.feature_names_[:8]}...")

    # 2. Random Forest (multiclass, class_weight balanced_subsample).
    rf_cfg = model_cfg.get("random_forest", {})
    if a.fast:
        rf_cfg = {**rf_cfg, "n_estimators": 20}
    rf = RandomForestModel(**{k: v for k, v in rf_cfg.items() if k != "random_state"}, random_state=a.seed)
    rf.fit(X_train, y_train, classes=classes)
    rf.save(model_dir, extra={"dataset_version": data_cfg.get("version", "v1"),
                              "feature_schema_version": "v1", "label_classes": classes})
    print("RF trained.")

    # 3. Autoencoder on BENIGN TRAIN only; threshold on BENIGN VAL only.
    ae_cfg = model_cfg.get("autoencoder", {})
    benign_mask_tr = normalize_labels(train[label_col]).str.lower() == benign_label.lower()
    benign_mask_va = normalize_labels(val[label_col]).str.lower() == benign_label.lower()
    Xb_tr = X_train[np.asarray(benign_mask_tr)]
    Xb_va = X_val[np.asarray(benign_mask_va)]
    print(f"AE benign rows: train={len(Xb_tr)} val={len(Xb_va)}")
    ae_cap = int(ae_cfg.get("max_train_rows", 200000))
    if len(Xb_tr) > ae_cap:  # documented compute cap; threshold still uses FULL benign val
        stride = len(Xb_tr) / ae_cap
        idx = (np.arange(ae_cap) * stride).astype(int)
        Xb_tr = Xb_tr[idx]
        print(f"AE train stride-capped to {len(Xb_tr)} rows (deterministic, coverage-preserving).")
    ae = AutoencoderModel(input_dim=X_train.shape[1], hidden_dims=ae_cfg.get("hidden_dims", [64, 32, 16]),
                          learning_rate=ae_cfg.get("learning_rate", 1e-3),
                          batch_size=ae_cfg.get("batch_size", 256),
                          epochs=5 if a.fast else ae_cfg.get("epochs", 50),
                          patience=ae_cfg.get("patience", 8), seed=a.seed)
    if len(Xb_tr) >= 10 and len(Xb_va) >= 5:
        ae.fit(Xb_tr, Xb_va)
        ae.fit_threshold(Xb_va, strategy=ae_cfg.get("threshold_strategy", "percentile"),
                         percentile=ae_cfg.get("threshold_percentile", 95.0))
    else:
        print("WARNING: insufficient benign rows; AE threshold unset.")
    ae.save(model_dir, extra={"dataset_version": data_cfg.get("version", "v1")})
    print(f"AE trained. threshold={ae.threshold_}")

    # 4. Isolation Forest on BENIGN TRAIN; calibrated on BENIGN VAL.
    if_cfg = model_cfg.get("isolation_forest", {})
    iff = IsolationForestModel(n_estimators=20 if a.fast else if_cfg.get("n_estimators", 200),
                               random_state=a.seed)
    if len(Xb_tr) >= 10:
        iff.fit(Xb_tr)
        if len(Xb_va) >= 5:
            iff.calibrate(Xb_va)
    iff.save(model_dir, extra={"dataset_version": data_cfg.get("version", "v1")})
    print("IF trained.")

    # 5. LSTM on temporally-ordered sequences (label of last flow).
    lstm_cfg = model_cfg.get("lstm", {})
    seq_len = int(lstm_cfg.get("seq_len", 10))
    ts_col = lstm_cfg.get("timestamp_column", "Timestamp")
    seq_keys = lstm_cfg.get("sequence_keys", [])
    def _seq(df: pd.DataFrame, X: np.ndarray, yb: np.ndarray):
        ts = df[ts_col] if ts_col in df.columns else None
        grp = None
        if seq_keys and all(k in df.columns for k in seq_keys):
            grp = df[seq_keys].astype(str).agg("|".join, axis=1)
        return build_sequences(X, yb, timestamps=ts, groups=grp, seq_len=seq_len)
    Xstr, ystr = _seq(train, X_train, yb_train)
    Xsva, ysva = _seq(val, X_val, yb_val)
    if len(Xstr) < seq_len:  # fall back to global time order when contexts are too sparse
        Xstr, ystr = build_sequences(X_train, yb_train, timestamps=train[ts_col] if ts_col in train.columns else None, seq_len=seq_len)
        Xsva, ysva = build_sequences(X_val, yb_val, timestamps=val[ts_col] if ts_col in val.columns else None, seq_len=seq_len)
        print(f"LSTM fallback to global time order: train={len(Xstr)} val={len(Xsva)}")
    # Deterministic stride caps (documented): full CICIDS2017 windows exceed RAM.
    def _cap(Xs: np.ndarray, ys: np.ndarray, cap: int, name: str):
        if len(Xs) > cap:
            stride = len(Xs) / cap
            idx = (np.arange(cap) * stride).astype(int)
            print(f"LSTM {name}: stride-capped {len(Xs)} -> {cap} windows (deterministic, coverage-preserving).")
            return Xs[idx], ys[idx]
        return Xs, ys
    Xstr, ystr = _cap(Xstr, ystr, int(lstm_cfg.get("max_train_sequences", 300000)), "train")
    Xsva, ysva = _cap(Xsva, ysva, int(lstm_cfg.get("max_val_sequences", 60000)), "val")
    print(f"LSTM sequences: train={len(Xstr)} val={len(Xsva)}")
    lstm = None
    if len(Xstr) >= seq_len and len(Xsva) >= 1:
        lstm = LSTMModel(input_dim=X_train.shape[1], seq_len=seq_len,
                         hidden_size=lstm_cfg.get("hidden_size", 64),
                         dropout=lstm_cfg.get("dropout", 0.2),
                         learning_rate=lstm_cfg.get("learning_rate", 1e-3),
                         batch_size=lstm_cfg.get("batch_size", 256),
                         epochs=3 if a.fast else lstm_cfg.get("epochs", 30),
                         patience=lstm_cfg.get("patience", 6), seed=a.seed)
        lstm.fit(Xstr, ystr, Xsva, ysva)
        lstm.save(model_dir, extra={"dataset_version": data_cfg.get("version", "v1")})
        print("LSTM trained.")
    else:
        print("WARNING: insufficient sequences; LSTM skipped (ablation will note this factually).")

    # 6. Validation signals -> calibration + ensemble weights (VALIDATION ONLY).
    model_classes = list(rf.model.classes_)
    col = model_classes.index(bi) if bi in model_classes else None
    s_rf = rf_attack_probability(rf.predict_proba(X_val), col)
    signals = {"random_forest": s_rf}
    try:
        signals["autoencoder"] = ae.anomaly_score(X_val)
    except Exception as e:
        print(f"AE signal skipped: {e}")
    try:
        signals["isolation_forest"] = iff.anomaly_score(X_val)
    except Exception as e:
        print(f"IF signal skipped: {e}")
    cal = SigmoidCalibrator().fit(s_rf, yb_val)
    cal.save(model_dir / "rf_calibrator.joblib")
    signals["random_forest"] = cal.transform(s_rf)

    if ens_cfg.get("mode") == "validation_optimized":
        eng = EnsembleEngine(decision_threshold=ens_cfg.get("decision_threshold", 0.5))
        res = eng.optimize_weights(signals, yb_val, metric=ens_cfg.get("metric", "f1"))
        print(f"Optimised weights: {res}")
    else:
        eng = EnsembleEngine(weights=ens_cfg.get("manual_weights"),
                             decision_threshold=ens_cfg.get("decision_threshold", 0.5), mode="manual")
    eng.save(model_dir / "ensemble_config.json")

    commit = git_commit()
    for name, ver in (("flow_preprocessor", "v1"), ("random_forest", "v1.0.0"),
                      ("autoencoder", "v1.0.0"), ("isolation_forest", "v1.0.0"),
                      ("lstm", "v1.0.0" if lstm else "missing"), ("ensemble", "v1")):
        register_model(model_dir, {"model_name": name, "version": ver,
                                   "dataset_version": data_cfg.get("version", "v1"),
                                   "feature_schema_version": "v1", "seed": a.seed,
                                   "git_commit": commit, "training_seconds": round(time.time() - t0, 1)})
    print(f"Done in {time.time()-t0:.1f}s. Artifacts in {model_dir}")


if __name__ == "__main__":
    main()
