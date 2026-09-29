# Drift detection (PSI)

`ml/drift/psi.py`: per-feature PSI over reference-quantile bins with epsilon
stabilisation; aggregate mean (or max). Bands: <0.10 STABLE, 0.10-0.25
MODERATE, >=0.25 SEVERE (see `configs/drift.yaml`). PSI is advisory: it writes
`drift_events` rows and broadcasts WS updates but never mutates thresholds.
Adaptation (`none|pending|recalibrated|retraining`) is an explicit audited
action. The Drift page shows timeline, heatmap, top features with
interpretations, and event history. Controlled experiments live in
`evaluation/drift.py` (reference=val window, current=test window).
