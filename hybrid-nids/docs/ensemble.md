# Ensemble, calibration, risk

`ml/ensemble/score_normalizer.py` maps RF (1-P(benign)), AE
(threshold-anchored), IF (val min-max) and LSTM (sigmoid) to 0..1.
`ml/calibration/calibrator.py` applies Platt (sigmoid) calibration fitted on
VALIDATION RF scores. `ml/ensemble/ensemble.py` fuses with weights
(sum=1, >=0) in `manual` or `validation_optimized` (grid search on validation
F1/ROC-AUC; never test). Persisted to `ensemble_config.json` with mode,
metric and validation score. `ml/ensemble/risk_engine.py` maps risk to
LOW/MEDIUM/HIGH/CRITICAL bands (configurable) and emits an auditable decision
record with per-model signals. Every alert carries a generated explanation
sentence plus computed top-feature attributions (`ml/explainability`).
