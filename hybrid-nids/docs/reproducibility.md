# Reproducibility

Every run records: seed, configs (`configs/*.yaml` fingerprint), dataset
version + manifest sha256, feature list (`feature_schema.json`), model
versions (`model_registry.json`), protocol and metrics (`experiments/results`,
`experiments` table). Leakage guards: train-only fitting, validation-only
thresholds/calibration/weights, `_rowid` overlap assertions, unseen-family
train exclusion asserted. Regenerate: `prepare_data.py -> train_all.py --seed
S -> evaluate_all.py`. Synthetic data (`scripts/synthetic_data.py`, Demo Mode)
is watermarked and excluded from research results.
