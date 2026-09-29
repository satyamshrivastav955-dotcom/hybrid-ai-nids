# Model design

- **RandomForest** (`ml/models/random_forest.py`): multiclass supervised head,
  `class_weight=balanced_subsample`; reports precision/recall/F1/macro/micro,
  balanced accuracy, ROC/PR-AUC, MCC, FPR/FNR.
- **Autoencoder** (`ml/models/autoencoder.py`): 64-32-16-32-64 PyTorch MLP,
  trained on benign TRAIN only; threshold on benign VAL only
  (percentile | validation-FPR-target). Per-feature errors feed alert pages.
- **IsolationForest** (`ml/models/isolation_forest.py`): benign-only fit;
  decision scores min-max mapped with benign-VAL statistics to 0..1.
- **LSTM** (`ml/models/lstm.py` + `sequencing.py`): seq_len=10 windows
  `[x(t-9)..x(t)]` in timestamp order (optionally grouped by src/dst context,
  with global-order fallback); label = last flow. Never built from shuffled rows.

All learned statistics use train (fit) and validation (thresholds, calibration,
weights); test is read-only.
