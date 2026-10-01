"""Prediction API contract, authentication, health, and parity tests."""

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from app.ml.model_manager import get_model_manager
from ml_service.inference import predict_one
from ml_test_utils import MANIFEST, example_request


@pytest.fixture(scope="module")
def prediction_client():
    manager = get_model_manager()
    manager.clear()
    manager.load(MANIFEST)
    app.dependency_overrides[get_current_user] = lambda: object()
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def test_liveness_readiness_and_openapi(prediction_client):
    assert prediction_client.get("/health").json() == {"status": "alive"}
    readiness = prediction_client.get("/api/predictions/health")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["checksum_status"] == "verified"

    paths = prediction_client.get("/openapi.json").json()["paths"]
    assert "/api/predictions/" in paths
    assert "post" in paths["/api/predictions/"]


def test_readiness_returns_503_when_model_is_not_loaded(prediction_client):
    manager = get_model_manager()
    manager.clear()
    response = prediction_client.get("/api/predictions/health")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    manager.load(MANIFEST)


def test_prediction_requires_authentication(prediction_client):
    override = app.dependency_overrides.pop(get_current_user)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.post("/api/predictions/", json=example_request())
    finally:
        app.dependency_overrides[get_current_user] = override
    assert response.status_code == 401


def test_api_prediction_matches_direct_inference(prediction_client):
    payload = example_request()
    payload["actual_kwh"] = 123.45
    direct = predict_one(payload, MANIFEST)
    response = prediction_client.post("/api/predictions/", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["predicted_meter_reading"] == pytest.approx(
        direct["predicted_meter_reading"],
        abs=1e-12,
    )
    assert body["model_version"] == direct["model_version"]
    assert body["warnings"] == direct["warnings"]
    assert body["input_timestamp"].startswith(payload["timestamp"])
    assert body["processing_time_ms"] >= 0
    assert "confidence" not in body


def test_api_accepts_legacy_request_without_actual_reading(prediction_client):
    response = prediction_client.post("/api/predictions/", json=example_request())
    assert response.status_code == 200


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actual_kwh", -1),
        ("meter", 9),
        ("square_feet", -1),
        ("timestamp", "invalid"),
    ],
)
def test_invalid_input_has_safe_error_contract(
    prediction_client,
    field,
    value,
):
    payload = example_request()
    payload[field] = value
    response = prediction_client.post("/api/predictions/", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_PREDICTION_INPUT"
    assert body["error"]["request_id"]
    assert "traceback" not in response.text.lower()
