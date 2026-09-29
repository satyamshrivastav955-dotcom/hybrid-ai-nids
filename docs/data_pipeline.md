# Data pipeline

`scripts/prepare_data.py` implements: raw CSV concat -> interim parquet ->
protocol splits -> manifest (`data/metadata/manifest.json` with sha256, row
counts, class counts).

Protocols (`ml/preprocessing/splits.py`):
- `standard_stratified` (seeded shuffle, leakage asserted via `_rowid`),
- `temporal` (chronological sort on `Timestamp`),
- `unseen_attack` (configured families appear ONLY in test).

Feature pipeline (`ml/preprocessing/pipeline.py`, fitted on TRAIN only):
standardise -> drop identifiers -> inf->NaN -> numeric coerce ->
missing policy (train medians) -> dedup -> variance filter -> correlation
filter -> ranking (mutual_info/f_test/variance) -> top-K -> RobustScaler.
Persisted: `feature_selector.joblib`, `scaler.joblib`,
`label_encoder.joblib`, `feature_medians.joblib`, `feature_schema.json`.
Inference enforces the exact schema; live/demo rows with missing features are
median-imputed, logged and flagged (`imputed_features`).
