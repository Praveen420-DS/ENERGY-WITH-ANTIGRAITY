"""Production prediction request validation tests."""

import math

import pytest
from pydantic import ValidationError

from app.schemas.prediction import ProductionPredictionRequest
from ml_test_utils import example_request


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("meter", 4),
        ("square_feet", -1),
        ("year_built", 1700),
        ("floor_count", 0),
        ("timestamp", "not-a-date"),
        ("wind_direction", 361),
        ("air_temperature", math.nan),
        ("wind_speed", math.inf),
    ],
)
def test_invalid_contract_values_are_rejected(field, value):
    payload = example_request()
    payload[field] = value
    with pytest.raises(ValidationError):
        ProductionPredictionRequest.model_validate(payload)


def test_missing_field_and_target_are_rejected():
    missing = example_request()
    missing.pop("building_id")
    with pytest.raises(ValidationError):
        ProductionPredictionRequest.model_validate(missing)

    target = example_request()
    target["meter_reading"] = 42
    with pytest.raises(ValidationError):
        ProductionPredictionRequest.model_validate(target)


def test_timezone_aware_timestamp_is_rejected():
    payload = example_request()
    payload["timestamp"] = "2016-07-15T14:00:00+00:00"
    with pytest.raises(ValidationError, match="timezone-naive"):
        ProductionPredictionRequest.model_validate(payload)
