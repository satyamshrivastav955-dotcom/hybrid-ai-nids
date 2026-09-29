# Architecture

```
Network Flow Data (CICIDS2017 CSVs / PCAP / live NIC / demo)
  -> Dataset pipeline (data/) + manifest
  -> FlowPreprocessor (train-only fit; persisted selector/scaler/encoder)
  -> RandomForest (multiclass) | Autoencoder (benign recon) |
     IsolationForest (benign stats) | LSTM (ordered sequences)
  -> Score normalisation (0..1) -> Sigmoid calibration (val) ->
     EnsembleEngine (weighted fusion, val-optimised) -> RiskEngine (bands)
  -> Explainability + Threat-intel enrichment -> Alert lifecycle (DB)
  -> FastAPI (REST + WebSocket) + PostgreSQL -> React/Vite SOC (12 pages)
```

Cross-cutting: PSI drift monitoring (advisory events), model registry
(`models/model_registry.json`), file-based experiment tracking
(`experiments/results/*.json` + figures), structured logging with
request/alert trace ids.

Modularity: dataset, each model, drift method, intel provider and frontend
pages are replaceable behind small interfaces (`ThreatIntelProvider`,
`EnsembleEngine`, per-model `save`/`load`).
