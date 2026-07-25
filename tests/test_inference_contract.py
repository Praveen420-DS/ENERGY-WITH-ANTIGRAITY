import json
from pathlib import Path

import numpy as np
import pytest

from ml_service.inference import (InputValidationError, load_production_model,
                                  predict_one, validate_prediction_input)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "models/production/current.json"


@pytest.fixture
def example():
    loaded = load_production_model(MANIFEST)
    return json.loads((loaded.package_dir/"example_request.json").read_text())


@pytest.mark.parametrize("field", [
    "building_id", "meter", "timestamp", "site_id", "primary_use",
    "square_feet", "year_built", "floor_count", "air_temperature",
    "cloud_coverage", "dew_temperature", "precip_depth_1_hr",
    "sea_level_pressure", "wind_direction", "wind_speed",
])
def test_every_contract_field_is_required(example, field):
    example.pop(field)
    with pytest.raises(InputValidationError, match="Missing required fields"):
        validate_prediction_input(example)


@pytest.mark.parametrize(("field", "value"), [
    ("meter", 4), ("square_feet", -1), ("year_built", 1700),
    ("floor_count", 0), ("wind_direction", 361),
    ("air_temperature", np.nan), ("wind_speed", np.inf),
    ("timestamp", "impossible-date"), ("primary_use", ""),
])
def test_invalid_values_fail_clearly(example, field, value):
    example[field] = value
    with pytest.raises(InputValidationError):
        validate_prediction_input(example)


def test_target_and_extra_columns_are_rejected(example):
    example["meter_reading"] = 1.0
    with pytest.raises(InputValidationError, match="must not be supplied"):
        validate_prediction_input(example)


def test_unknown_categories_and_identifiers_are_safe(example):
    example.update(primary_use="Never seen use", building_id=999999, site_id=999999)
    response = predict_one(example, MANIFEST)
    assert response["predicted_meter_reading"] >= 0
    assert len(response["warnings"]) == 3


def test_request_key_order_does_not_change_prediction(example):
    reordered = {key: example[key] for key in reversed(list(example))}
    assert predict_one(example, MANIFEST)["predicted_meter_reading"] == \
           predict_one(reordered, MANIFEST)["predicted_meter_reading"]
