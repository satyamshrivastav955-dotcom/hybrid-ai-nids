"""Demo traffic generator. SYNTHETIC ONLY — every event carries source='demo'."""
from __future__ import annotations

import random
import time


def demo_flow(i: int) -> dict:
    attack = i % 7 == 3
    return {
        "features": {
            "Flow Duration": random.uniform(10, 5000 if attack else 800),
            "Total Fwd Packets": random.uniform(1, 900 if attack else 40),
            "Flow Bytes/s": random.uniform(50000, 900000) if attack else random.uniform(100, 9000),
            "SYN Flag Count": random.randint(3, 25) if attack else random.randint(0, 2),
            "Destination Port": random.choice([4444, 22, 3389]) if attack else 80,
        },
        "src_ip": f"203.0.113.{random.randint(2, 250)}",
        "dst_ip": f"192.168.10.{random.randint(2, 60)}",
        "src_port": random.randint(1024, 65535),
        "dst_port": 4444 if attack else 80,
        "protocol": "TCP",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
