# Measured results — CICIDS2017 (seed 42)

> All numbers below are measured artifacts in `experiments/results/*.json`
> (reproduce: `prepare_data.py → train_all.py --seed 42 → evaluate_all.py`).
> Dataset: GeneratedLabelledFlows, 8 files, 3,119,345 rows loaded, 2,830,743
> usable (288,602 empty filler rows in the Thursday-morning file dropped and
> documented). 12 classes, benign majority (2.27M) down to 11 Heartbleed rows.
> Standard test n=566,149. No number here is invented.

## Standard stratified (binary benign vs attack)

| Model | Acc | Prec | Rec | F1 | MCC | ROC-AUC | PR-AUC | FPR |
|---|---|---|---|---|---|---|---|---|
| RandomForest | 0.9994 | 0.9978 | 0.9991 | 0.9984 | 0.9981 | 1.0000 | 1.0000 | 0.0005 |
| Autoencoder (op 0.5) | 0.8030 | 0.0000 | 0.0000 | 0.0000 | −0.0007 | 0.6867 | 0.3521 | 0.0000 |
| IsolationForest | 0.8394 | 0.6335 | 0.4387 | 0.5184 | 0.4362 | 0.6920 | 0.4385 | 0.0623 |
| Ensemble (0.7/0.3/0/0) | 0.9995 | 0.9996 | 0.9980 | 0.9988 | 0.9985 | 1.0000 | 1.0000 | 0.0001 |

Reading: RF dominates known-attack classification. The ensemble adds a small
but operationally meaningful FPR reduction (0.0005 → 0.0001). AE/IF are weak
standalone at the fixed 0.5 operating point (ROC ≈ 0.69); the validation-tuned
ensemble still extracts value from AE (weight 0.3) and assigns IF/LSTM zero
weight — see ablation.

## Ablation (equal weights unless noted)

RF 0.9981 · IF 0.5184 · RF+AE 0.9750 · RF+IF 0.9948 · RF+AE+IF 0.6093 ·
trained-weights 0.9988. Conclusion: naive equal-weight fusion of weak anomaly
signals HURTS (0.6093); validation-optimised fusion is required. AE needs a
transported operating threshold (recorded future work).

## Unseen attack (Infiltration held out of train/val entirely, n=36 in test)

Known: F1 0.9989. Unseen: precision 0.365 / recall 0.639 / F1 0.465 at
FPR 0.0001. Honest zero-day reading: ~2/3 of never-seen Infiltration flows
detected, with low precision — anomaly detection, not classification.
Reported separately, never merged.

## Temporal (train Mon–Thu → val Thu → test Fri; test = 703,245 rows, 41% attacks)

Ensemble: train F1 0.9994 → val (Thu WebAttacks) 0.9822 → test (Fri
DDoS/PortScan/Bot) 0.9998, FPR 0.0 in all windows. LSTM sequences: val
(Thu) F1 0.9252, test (Fri) F1 0.9973 over 585,804 ordered windows.
No temporal collapse on this cut.

## Drift

Stratified val→test: PSI 0.00 STABLE (expected — same distribution).
Inter-day Thu→Fri: PSI 0.21 MODERATE, led by packet/header-length features.
PSI flagged the shift without any performance collapse — advisory role
confirmed; no thresholds were auto-mutated.

## Latency (500-row batches, RTX 4050 laptop + i5)

Preprocess 17.0ms · RF 97.1ms · AE 0.5ms · IF 21.6ms · ensemble 0.06ms ·
total ≈115ms/500 rows ≈ **0.23ms/flow (~4,300 flows/s)**. Sub-millisecond per
flow on this hardware — measured, not assumed. Single-row API path adds HTTP/DB
overhead on top.

## Limitations of these numbers

- Two seeds run (42, 43): ensemble F1 = **0.9986 ± 0.0003** (0.9988 / 0.9984),
  RF F1 = 0.9984 / 0.9985, FPR 0.0001 both seeds. Stable; more seeds would
  tighten this further.
- Infiltration holdout is tiny (36 rows); a Bot-holdout rerun would strengthen RQ7.
- AE operating threshold transport is future work (standalone AE F1 0 at 0.5).
- Timestamps carry a documented D/M parsing quirk handled with mixed-format parsing.
