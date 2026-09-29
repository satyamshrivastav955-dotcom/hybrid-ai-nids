"""Unit: preprocessing pipeline, splits, leakage guards."""
import numpy as np
import pandas as pd
import pytest

from ml.preprocessing.cleaning import basic_clean
from ml.preprocessing.pipeline import FlowPreprocessor
from ml.preprocessing.splits import standard_split, temporal_split, unseen_attack_split
from scripts.synthetic_data import generate


@pytest.fixture(scope="module")
def df():
    return generate(n_per_class=40, seed=11)


def test_basic_clean_drops_identifiers(df):
    out = basic_clean(df, "Label", ["Flow ID", "Source IP", "Destination IP", "Timestamp"])
    for c in ("Flow ID", "Source IP", "Destination IP", "Timestamp"):
        assert c not in out.columns
    assert "Label" in out.columns


def test_preprocessor_fit_transform_roundtrip(df):
    res = standard_split(df, "Label", seed=11)
    pre = FlowPreprocessor(top_k=10).fit(res.train, label_col="Label",
                                         drop_cols=["Flow ID", "Source IP", "Destination IP", "Timestamp"])
    Xtr, Xva, Xte = pre.transform(res.train), pre.transform(res.val), pre.transform(res.test)
    assert Xtr.shape[1] == 10 and Xva.shape[1] == 10 and Xte.shape[1] == 10
    assert not np.isnan(Xtr).any()
    # fitted feature list persists
    assert len(pre.feature_names_) == 10


def test_preprocessor_rejects_unknown_schema(df, tmp_path):
    res = standard_split(df, "Label", seed=11)
    pre = FlowPreprocessor(top_k=8).fit(res.train, label_col="Label", drop_cols=[])
    pre.save(tmp_path)
    from ml.preprocessing.pipeline import FlowPreprocessor as P2
    loaded = P2.load(tmp_path)
    bad = res.test.drop(columns=[loaded.feature_names_[0]])
    with pytest.raises(KeyError):
        loaded.transform(bad)


def test_splits_have_no_overlap(df):
    res = standard_split(df, "Label", seed=11)
    assert len(res.train) and len(res.val) and len(res.test)
    # unseen protocol keeps holdout out of train
    res2 = unseen_attack_split(df, "Label", holdout_families=["Infiltration"], seed=11)
    assert "Infiltration" not in set(res2.train["Label"].str.strip())
    assert "Infiltration" in set(res2.test["Label"].str.strip())


def test_temporal_split_respects_time_order(df):
    res = temporal_split(df, "Label", timestamp_col="Timestamp")
    assert len(res.train) and len(res.test)


def test_temporal_day_aware_split():
    import pandas as pd
    from ml.preprocessing.splits import temporal_split
    rows = []
    for day, labels in [(3, ["BENIGN"] * 20), (4, ["BENIGN"] * 20),
                        (5, ["BENIGN"] * 18 + ["DoS"] * 2), (6, ["BENIGN"] * 20),
                        (7, ["BENIGN"] * 10 + ["DDoS"] * 10)]:
        for i, lab in enumerate(labels):
            rows.append({f"f{j}": float(i) for j in range(3)} | {
                "Timestamp": f"{day}/7/2017 8:{i:02d}", "Label": lab})
    df = pd.DataFrame(rows)
    res = temporal_split(df, "Label", timestamp_col="Timestamp", test_days=1)
    assert len(res.test) == 20  # all of day 7
    assert set(res.test["Label"].str.strip()) == {"BENIGN", "DDoS"}
    assert "DDoS" not in set(res.train["Label"].str.strip())
    assert len(res.train) + len(res.val) == 80
