# Deployment

Local: backend `uvicorn backend.app.main:app` (SQLite default), frontend
`npm run dev` (proxies `/api` + direct WS to :8000). Production: set
`DATABASE_URL` to PostgreSQL, `API_KEY` for header auth, provider keys; run
`docker compose -f docker/docker-compose.yml up --build` (postgres, backend,
frontend+nginx on :8080). Models mount read-only; artifacts are never loaded
from user uploads (trusted local `models/` only). Live capture: run a flow
exporter (e.g. CICFlowMeter/scapy job) mapping to the trained schema and POST
to `/predict/batch` (see `scripts/replay.py`); schema gaps are imputed, logged
and flagged. Demo Mode: frontend mode switch + `replay.py --mode demo`
(synthetic, always labelled DEMO).
