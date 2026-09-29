"""Model registry: versioned metadata for every trained artifact."""
from __future__ import annotations

import datetime
import json
from pathlib import Path


def register_model(model_dir: str | Path, entry: dict) -> dict:
    d = Path(model_dir)
    d.mkdir(parents=True, exist_ok=True)
    reg_path = d / "model_registry.json"
    registry = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.exists() else []
    entry = {"registered_at": datetime.datetime.utcnow().isoformat() + "Z", **entry}
    registry.append(entry)
    reg_path.write_text(json.dumps(registry, indent=2, default=str), encoding="utf-8")
    return entry


def list_models(model_dir: str | Path) -> list[dict]:
    reg_path = Path(model_dir) / "model_registry.json"
    if not reg_path.exists():
        return []
    return json.loads(reg_path.read_text(encoding="utf-8"))
