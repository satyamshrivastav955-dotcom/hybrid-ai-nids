# experiments/

`results/` holds machine-readable outputs (`standard_metrics.json`,
`unseen_attack_metrics.json`, `temporal_metrics.json`, `drift_metrics.json`,
`ablation_metrics.json`, `latency_metrics.json`); `figures/` holds PNGs.
Populated by `python scripts/evaluate_all.py`. Empty until a real evaluation
runs — by design, no numbers are pre-filled.
