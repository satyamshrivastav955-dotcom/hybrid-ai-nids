# hybrid-ai-nids

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688)
![React](https://img.shields.io/badge/React-18-61dafb)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Tests](https://img.shields.io/badge/tests-22%20passed-brightgreen)

Research-grade hybrid network intrusion detection (Random Forest + autoencoder + Isolation Forest + LSTM) with decision-level fusion, PSI drift monitoring, threat-intel enrichment and a 12-page SOC dashboard — evaluated on CICIDS2017.

## Start here

Everything lives in [`hybrid-nids/`](hybrid-nids/) — start with its [README](hybrid-nids/README.md):

- **Run it:** install → prepare CICIDS2017 data → train → evaluate → launch API + dashboard (commands in the project README).
- **Results:** measured numbers in [`hybrid-nids/docs/results.md`](hybrid-nids/docs/results.md) — ensemble F1 0.9988 @ FPR 0.0001, unseen-attack recall 0.64, Friday temporal F1 0.9998, ~0.23 ms/flow.
- **Docs:** architecture, data pipeline, model design, evaluation and reproducibility notes in [`hybrid-nids/docs/`](hybrid-nids/docs/).

```powershell
cd hybrid-nids
pip install -r requirements.txt
python scripts/prepare_data.py --raw data/raw --out data --protocol all
python scripts/train_all.py --seed 42
python scripts/evaluate_all.py
uvicorn backend.app.main:app --port 8000
```

No datasets, model artifacts, or secrets are committed — see `.gitignore` and `data/README.md`.
