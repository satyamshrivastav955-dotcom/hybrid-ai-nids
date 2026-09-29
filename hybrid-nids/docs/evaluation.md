# Evaluation methodology

Modules (`evaluation/`): `standard` (stratified test, all models + ensemble),
`unseen_attack` (known vs held-out families reported SEPARATELY, never merged),
`temporal` (train/val/test windows to quantify degradation), `drift`
(baseline vs shifted PSI + performance), `ablation` (RF/AE/IF/LSTM alone and
combinations + trained weights), `latency` (mean/median/p95/p99 + throughput).

Metrics (`evaluation/metrics.py`): accuracy, precision, recall, F1,
macro/weighted-F1, balanced accuracy, ROC/PR-AUC, MCC, FPR, FNR, detection
rate; NaN-safe. Figures in `experiments/figures/` (confusion matrix, ROC, PR, calibration,
ablation F1, PSI timeline, score histograms). Served to the SOC via
`GET /models/figures/{name}`. Run:
`python scripts/evaluate_all.py` (or per-module `python -m evaluation.<name>`).
Multi-seed reporting: re-run with `--seed` variants and aggregate with
`summarize_runs`. No metric is claimed without an experiment artifact.
