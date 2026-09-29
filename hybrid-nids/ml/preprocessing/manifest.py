"""Dataset manifest: checksums, row/feature counts, class distribution."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    files: list[Path],
    label_col: str | None,
    out_path: Path,
    extra: dict | None = None,
) -> dict:
    entries = []
    for fp in files:
        df = pd.read_parquet(fp) if fp.suffix == ".parquet" else pd.read_csv(fp)
        entry = {
            "file": fp.name,
            "sha256": sha256_file(fp),
            "rows": int(len(df)),
            "columns": int(df.shape[1]),
            "features": [c for c in df.columns if c != label_col],
        }
        if label_col and label_col in df.columns:
            entry["class_counts"] = df[label_col].astype(str).str.strip().value_counts().to_dict()
        entries.append(entry)
    manifest = {
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "files": entries,
        "extra": extra or {},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest
