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


def test_actual_kwh_is_optional_nonnegative_and_excluded_from_inference():
    payload = {
        "building_id": 0,
        "meter": 0,
        "timestamp": "2016-07-15T14:00:00",
        "site_id": 0,
        "primary_use": "Education",
        "square_feet": 7432,
        "year_built": 2008,
        "floor_count": 4,
        "air_temperature": 25,
        "cloud_coverage": 6,
        "dew_temperature": 20,
        "precip_depth_1_hr": 0,
        "sea_level_pressure": 1019.7,
        "wind_direction": 180,
        "wind_speed": 3.1,
    }
    payload["actual_kwh"] = 42.5
    request = ProductionPredictionRequest.model_validate(payload)

    assert request.actual_kwh == 42.5
    assert "actual_kwh" not in request.to_inference_record()
    legacy_payload = {key: value for key, value in payload.items() if key != "actual_kwh"}
    assert ProductionPredictionRequest.model_validate(legacy_payload).actual_kwh is None

    payload["actual_kwh"] = -0.1
    with pytest.raises(ValidationError):
        ProductionPredictionRequest.model_validate(payload)
