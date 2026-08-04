import json
from pathlib import Path

import pytest

from scripts.phase2_train_electricity_models import consumption_band, load_schema, select_best, split_name


def test_chronological_boundaries():
    import pandas as pd
    assert split_name(pd.Timestamp("2016-08-31 23:59:59")) == "training"
    assert split_name(pd.Timestamp("2016-09-01")) == "validation"
    assert split_name(pd.Timestamp("2016-10-31 23:59:59")) == "validation"
    assert split_name(pd.Timestamp("2016-11-01")) == "testing"


def test_consumption_bands():
    thresholds = {"small_max": 10, "medium_max": 50, "large_max": 100}
    assert [consumption_band(v, thresholds) for v in (0, 11, 51, 101)] == ["small", "medium", "large", "peak"]


def test_selection_tie_break_order():
    results = {
        "a": {"status": "trained", "validation": {"mae": 2, "rmsle": 1, "r2": .5}},
        "b": {"status": "trained", "validation": {"mae": 2, "rmsle": .9, "r2": .4}},
        "c": {"status": "trained", "validation": {"mae": 3, "rmsle": .1, "r2": .9}},
    }
    assert select_best(results) == "b"


def test_schema_rejects_meter_or_target_leakage(tmp_path: Path):
    base = {"meter_removed_from_predictors": True, "target_derived_features": False, "numeric_feature_columns": ["x"], "categorical_feature_columns": ["category"], "target_column": "meter_reading", "timestamp_column": "timestamp"}
    path = tmp_path / "schema.json"; path.write_text(json.dumps(base))
    assert load_schema(path) == (["x"], ["category"], "meter_reading", "timestamp")
    base["numeric_feature_columns"] = ["meter"]
    path.write_text(json.dumps(base))
    with pytest.raises(ValueError, match="Forbidden"):
        load_schema(path)
