"""Shared fixtures: tiny SYNTHETIC dataset + fast-trained models in tmp dirs.

Clearly marked synthetic; used for tests and smoke runs only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def synthetic_project(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("nids_test")
    splits = tmp / "splits"
    models = tmp / "models"
    splits.mkdir()
    # minimal splits via library calls (fast, no subprocess)
    sys.path.insert(0, str(ROOT))
    from scripts.synthetic_data import generate
    from ml.preprocessing.splits import persist_splits, standard_split
    df = generate(n_per_class=40, seed=7)
    res = standard_split(df, "Label", test_size=0.2, val_size=0.2, seed=7)
    persist_splits(res, splits, "cicids2017")
    persist_splits(res, splits, "cicids2017_temporal")
    # fast training in-process by invoking the script entry with argv patch
    import scripts.train_all as t
    argv = sys.argv
    sys.argv = ["train_all", "--splits", str(splits), "--models", str(models),
                "--base", "cicids2017", "--seed", "7", "--fast"]
    try:
        import os
        cwd = os.getcwd()
        os.chdir(ROOT)
        t.main()
    finally:
        sys.argv = argv
        os.chdir(cwd)
    return {"splits": splits, "models": models, "root": tmp}
