"""Replay flows into a running API (dataset mode) or generate demo traffic.

Dataset replay (uses the SAME schema path as training):
  python scripts/replay.py --mode dataset --splits data/splits --base cicids2017 --n 50 --url http://localhost:8000

Demo traffic (SYNTHETIC, labelled source=demo):
  python scripts/replay.py --mode demo --n 50 --url http://localhost:8000

Live capture (requires scapy + root/Npcap; maps packets to flow features):
  documented in docs/deployment.md; uses the same /predict contract.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
import pandas as pd


def dataset_flows(splits: Path, base: str, n: int, feature_names: list[str]) -> list[dict]:
    df = pd.read_parquet(splits / f"{base}_test.parquet")
    # Stride sample across the whole file (head() would only cover one time slice).
    step = max(1, len(df) // n)
    df = df.iloc[::step].head(n)
    out = []
    for _, row in df.iterrows():
        feats = {f: (float(row[f]) if f in row and pd.notna(row[f]) else 0.0) for f in feature_names}
        out.append({"features": feats,
                    "src_ip": str(row.get("Source IP", "10.0.0.1")),
                    "dst_ip": str(row.get("Destination IP", "192.168.10.10")),
                    "protocol": "TCP", "source": "dataset"})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dataset", "demo"], default="demo")
    ap.add_argument("--splits", default="data/splits")
    ap.add_argument("--base", default="cicids2017")
    ap.add_argument("--models", default="models")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--delay", type=float, default=0.2)
    a = ap.parse_args()

    if a.mode == "demo":
        import sys
        sys.path.insert(0, ".")
        from backend.app.services.demo import demo_flow
        flows = [{**demo_flow(i), "source": "demo"} for i in range(a.n)]
    else:
        schema = json.loads((Path(a.models) / "feature_schema.json").read_text())
        flows = dataset_flows(Path(a.splits), a.base, a.n, schema["feature_names"])
    print(f"Replaying {len(flows)} {a.mode} flows -> {a.url}")
    with httpx.Client(timeout=30) as c:
        for i in range(0, len(flows), 20):
            r = c.post(f"{a.url}/predict/batch", json={"flows": flows[i:i + 20], "source": a.mode})
            print(f"batch {i // 20}: {r.status_code} alerts={sum(1 for x in r.json().get('results', []) if x.get('alert_uid'))}")
            time.sleep(a.delay)


if __name__ == "__main__":
    main()
