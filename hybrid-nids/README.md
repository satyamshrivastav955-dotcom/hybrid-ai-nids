# Hybrid AI Network Intrusion Detection & Adaptive SOC

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688)
![React](https://img.shields.io/badge/React-18-61dafb)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow)
![Tests](https://img.shields.io/badge/tests-22%20passed-brightgreen)

Research-grade hybrid NIDS combining **Random Forest** (known-attack classification),
**Deep Autoencoder** (benign reconstruction anomaly), **Isolation Forest** (statistical
anomaly) and **LSTM** (temporal patterns) with decision-level fusion, PSI drift
monitoring, threat-intel enrichment, and a 12-page SOC dashboard.

```
Flow Data -> Preprocessing -> RF | AE | IF | LSTM -> Ensemble -> Risk ->
PSI drift -> Intel enrichment -> Alerts -> FastAPI + WS -> React SOC
```

> **Honesty contract:** no fabricated metrics. Until you run training +
> evaluation on real CICIDS2017 data, the UI shows *"No evaluation run yet"*.
> Demo Mode traffic is synthetic and always labelled DEMO. "Zero-day" is only
> claimed via the held-out `unseen_attack` protocol.

## Features

Known-attack classification, reconstruction + statistical anomaly detection,
temporal detection, validation-optimised fusion, risk bands, PSI drift console,
pluggable threat intel (mock/AbuseIPDB), RF/SHAP-style + reconstruction
explainability, alert lifecycle (new/investigating/acknowledged/resolved/dismissed),
live traffic view, historical analysis, ablation/unseen/temporal/drift/latency
evaluations, dataset + live + demo ingestion, REST + WebSocket, PostgreSQL,
Docker Compose, 17 automated tests.

## System requirements

Python 3.10+, Node 18+, 8GB RAM. Docker optional (no Docker daemon required for local run).

## Installation

```bash
cd hybrid-nids
pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env
```

## Dataset setup (CICIDS2017)

Download the CICIDS2017 flow CSVs into `data/raw/`, then:

```bash
python scripts/prepare_data.py --raw data/raw --out data --protocol all
```

Smoke-test without real data (synthetic, DEMO only):

```bash
python scripts/prepare_data.py --synthetic --n 120 --protocol all
```

## Training

```bash
python scripts/train_all.py --splits data/splits --models models --base cicids2017 --seed 42
# fast smoke variant: add --fast
```

Artifacts in `models/`: selector/scaler/encoder, `random_forest.joblib`,
`autoencoder.pth`, `isolation_forest.joblib`, `lstm_model.pth`,
`rf_calibrator.joblib`, `ensemble_config.json`, `model_registry.json`.

## Evaluation

```bash
python scripts/evaluate_all.py --splits data/splits --models models --base cicids2017
# or per-module: python -m evaluation.standard | unseen_attack | temporal | drift | ablation | latency
# LSTM sequences: python scripts/evaluate_lstm.py
```

Results: `experiments/results/*.json`, figures: `experiments/figures/`.

## Results (measured on CICIDS2017, seed 42)

Standard test (n=566k): RF F1 **0.9984**, ensemble F1 **0.9988** at FPR **0.0001**.
Unseen Infiltration holdout: recall **0.64** at FPR 0.0001 (anomaly-grade, honestly reported).
Temporal Fri test (703k rows, 41% attacks): ensemble F1 **0.9998**, LSTM F1 **0.9973**.
Drift Thu→Fri: PSI **0.21 MODERATE**, no performance collapse.
Latency: **~0.23ms/flow (~4,300 flows/s)** measured. Full tables: `docs/results.md`.

## Running the API / frontend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev   # http://localhost:5173
```

Demo traffic: `python scripts/replay.py --mode demo --n 50` (labels source=demo).
Dataset replay: `python scripts/replay.py --mode dataset --n 50`.

## Docker

```bash
docker compose -f docker/docker-compose.yml up --build
# frontend :8080, backend :8000, postgres :5432
```

## Testing

```bash
python -m pytest tests/ -q   # 17 tests: preprocessing, models, ensemble, PSI, API e2e, WS
```

## Configuration

`configs/`: `data.yaml`, `features.yaml`, `models.yaml`, `ensemble.yaml`,
`drift.yaml`, `system.yaml`. Secrets only via environment (`.env`).

## Security

Validated schemas, CORS allowlist, 300 req/min/IP rate limiting, optional
`X-API-Key` auth (`API_KEY` env), trusted-local model loading only, audit logs
for alert transitions, no secrets committed.

## Limitations & risks

- Needs real CICIDS2017 data for valid results; ships with no trained-on-real models.
- LSTM needs timestamped sequences; sparse contexts fall back to global time order.
- Mock intel is a placeholder; live intel needs API keys.
- SQLite default is dev-only; use PostgreSQL in production.
- No claim of production readiness; see docs for hardening checklist.

## Reproducibility

Seeds, config fingerprints, dataset manifest (sha256), feature schema, model
registry, per-protocol metrics — see `docs/reproducibility.md` and
`docs/evaluation.md`.
