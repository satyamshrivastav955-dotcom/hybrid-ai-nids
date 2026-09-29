"""Synthetic CICIDS2017-like flow generator.

PURPOSE: tests, Demo Mode, offline smoke runs. NEVER research evaluation.
Every output file/row is watermarked synthetic=True and the docs + UI label
it DEMO. Real evaluation requires the genuine CICIDS2017 CSVs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ATTACKS = ["BENIGN", "DoS", "PortScan", "BruteForce", "Infiltration", "WebAttack", "Bot"]

FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Mean", "Bwd Packet Length Mean", "Flow Bytes/s",
    "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Fwd IAT Mean",
    "Bwd IAT Mean", "SYN Flag Count", "ACK Flag Count", "PSH Flag Count",
    "FIN Flag Count", "Destination Port", "Packet Length Mean",
    "Average Packet Size", "Subflow Fwd Bytes", "Subflow Bwd Bytes",
    "Init_Win_bytes_forward", "Init_Win_bytes_backward", "Flow Duration MS",
]


def generate(n_per_class: int = 300, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    base_time = pd.Timestamp("2017-07-03 09:00:00")
    i = 0
    for label in ATTACKS:
        for _ in range(n_per_class):
            shift = {"BENIGN": 0.0, "DoS": 2.2, "PortScan": 1.4, "BruteForce": 1.0,
                     "Infiltration": 1.8, "WebAttack": 1.2, "Bot": 1.6}[label]
            feats = {}
            for f in FEATURES:
                loc = shift if f not in ("Destination Port",) else (80 if label == "BENIGN" else 4444)
                feats[f] = float(abs(rng.normal(loc=loc, scale=1.0)) + (0.5 if label != "BENIGN" else 0.1))
            feats["Flow ID"] = f"synth-{i}"
            feats["Source IP"] = f"10.0.{rng.integers(0, 5)}.{rng.integers(2, 250)}"
            feats["Destination IP"] = f"192.168.10.{rng.integers(2, 60)}"
            feats["Timestamp"] = str(base_time + pd.Timedelta(seconds=int(i * 7)))
            feats["Label"] = label
            feats["synthetic"] = True
            rows.append(feats)
            i += 1
    df = pd.DataFrame(rows).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return df
