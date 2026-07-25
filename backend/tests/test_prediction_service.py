"""Production prediction service tests."""

import math

import pytest

from app.ml.model_manager import ProductionModelManager
from app.schemas.prediction import ProductionPredictionRequest
from app.services.prediction_service import (
    PredictionProcessingError,
    PredictionService,
)
from ml_test_utils import MANIFEST, example_request


@pytest.fixture(scope="module")
def manager():
    instance = ProductionModelManager()
    instance.load(MANIFEST)
    return instance


def test_valid_prediction_is_finite_nonnegative_and_deterministic(manager):
    request = ProductionPredictionRequest.model_validate(example_request())
    first = PredictionService.predict(request, manager, "request-one")
    second = PredictionService.predict(request, manager, "request-two")

    assert math.isfinite(first.predicted_meter_reading)
    assert first.predicted_meter_reading >= 0
    assert first.predicted_meter_reading == pytest.approx(
        second.predicted_meter_reading,
        abs=1e-12,
    )
    assert first.model_version == manager.version
    assert first.input_timestamp == request.timestamp
    assert first.processing_time_ms >= 0
    assert first.request_id == "request-one"


def test_unknown_category_and_identifiers_preserve_warnings(manager):
    payload = example_request()
    payload.update(
        primary_use="Never seen use",
        building_id=999999,
        site_id=999999,
    )
    response = PredictionService.predict(
        ProductionPredictionRequest.model_validate(payload),
        manager,
    )
    assert len(response.warnings) == 3


def test_unexpected_inference_error_is_safely_mapped(manager, monkeypatch):
    request = ProductionPredictionRequest.model_validate(example_request())

    def fail(*args, **kwargs):
        raise RuntimeError("internal detail")

    monkeypatch.setattr(
        "app.services.prediction_service.predict_one",
        fail,
    )
    with pytest.raises(
        PredictionProcessingError,
        match="could not be completed",
    ):
        PredictionService.predict(request, manager)
