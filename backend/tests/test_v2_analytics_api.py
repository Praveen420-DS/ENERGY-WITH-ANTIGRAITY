from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.dependencies import get_current_user
from app.main import create_app
from app.config import Settings
from fastapi.testclient import TestClient


def test_anomaly_detection_and_peak_prediction_routes(monkeypatch):
    async def detect(*args):
        return {"examined_records": 4, "detected_count": 0, "anomalies": []}
    async def peak(*args):
        return {"meter_id": 2, "generated_at": datetime.now(timezone.utc),
                "peak_timestamp": datetime.now(timezone.utc), "forecast_kwh": 3,
                "peak_threshold_kwh": 5, "baseline_kwh": 3, "is_peak_likely": False,
                "horizon_records": 1, "history_records": 4}
    monkeypatch.setattr("app.routers.anomalies.AnomalyService.detect_anomalies", detect)
    monkeypatch.setattr("app.routers.peaks.PeakPredictionService.predict", peak)
    app = create_app(Settings())
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    client = TestClient(app)
    assert client.post("/api/anomalies/detect", json={}).status_code == 200
    response = client.post("/api/peaks/predict", json={"meter_id": 2})
    assert response.status_code == 200
    assert response.json()["forecast_kwh"] == 3


def test_v2_routes_require_authentication():
    client = TestClient(create_app(Settings()))
    assert client.post("/api/anomalies/detect", json={}).status_code == 401
    assert client.post("/api/peaks/predict", json={"meter_id": 1}).status_code == 401


def test_authenticated_anomaly_flow_persists_idempotently(client, auth_headers):
    first_timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def create_meter(label):
        response = client.post(
            "/api/meters/",
            headers=auth_headers,
            json={"meter_id": f"{label}-{uuid4()}", "name": "Test meter",
                  "location": "Test facility", "capacity_kw": 100},
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def add_observations(meter_id, values, start_offset=0):
        for offset, consumption in enumerate(values):
            response = client.post(
                "/api/energy/records",
                headers=auth_headers,
                json={"meter_id": meter_id, "consumption_kwh": consumption,
                      "timestamp": (first_timestamp + timedelta(hours=start_offset + offset)).isoformat()},
            )
            assert response.status_code == 201, response.text

    meter_id = create_meter("v2-anomaly")
    add_observations(meter_id, [10, 10, 9, 11, 10, 100])
    request = {"meter_id": meter_id, "limit": 100, "threshold": 3.5}
    first = client.post("/api/anomalies/detect", headers=auth_headers, json=request)
    second = client.post("/api/anomalies/detect", headers=auth_headers, json=request)
    assert first.status_code == second.status_code == 200
    assert first.json()["examined_records"] == second.json()["examined_records"] == 6
    assert len(first.json()["anomalies"]) == len(second.json()["anomalies"]) == 1
    assert first.json()["anomalies"][0]["id"] == second.json()["anomalies"][0]["id"]
    assert first.json()["anomalies"][0]["actual_kwh"] == 100

    add_observations(meter_id, [1000], start_offset=6)
    expanded = client.post("/api/anomalies/detect", headers=auth_headers, json=request)
    assert expanded.status_code == 200
    assert len(expanded.json()["anomalies"]) == 2
    assert expanded.json()["anomalies"][0]["id"] == first.json()["anomalies"][0]["id"]

    second_meter_id = create_meter("v2-anomaly-other-meter")
    add_observations(second_meter_id, [10, 10, 9, 11, 10, 100])
    other_meter = client.post(
        "/api/anomalies/detect", headers=auth_headers,
        json={"meter_id": second_meter_id, "limit": 100, "threshold": 3.5},
    )
    assert other_meter.status_code == 200
    assert len(other_meter.json()["anomalies"]) == 1
    assert other_meter.json()["anomalies"][0]["timestamp"] == first.json()["anomalies"][0]["timestamp"]
    stored = client.get("/api/anomalies/", headers=auth_headers)
    assert stored.status_code == 200
    assert sum(row["meter_id"] == meter_id for row in stored.json()) == 2
    assert sum(row["meter_id"] == second_meter_id for row in stored.json()) == 1


def test_authenticated_peak_flow_reads_history_and_returns_future_peak(client, auth_headers):
    meter_response = client.post(
        "/api/meters/",
        headers=auth_headers,
        json={"meter_id": f"v2-peak-{uuid4()}", "name": "Peak test meter",
              "location": "Test facility", "capacity_kw": 100},
    )
    assert meter_response.status_code == 201, meter_response.text
    meter_id = meter_response.json()["id"]
    first_timestamp = datetime(2025, 2, 1, tzinfo=timezone.utc)
    for offset, consumption in enumerate([2, 4, 6, 8]):
        response = client.post(
            "/api/energy/records",
            headers=auth_headers,
            json={"meter_id": meter_id, "consumption_kwh": consumption,
                  "timestamp": (first_timestamp + timedelta(hours=offset)).isoformat()},
        )
        assert response.status_code == 201, response.text

    result = client.post(
        "/api/peaks/predict", headers=auth_headers,
        json={"meter_id": meter_id, "horizon_records": 3},
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["history_records"] == 4
    assert body["horizon_records"] == 3
    assert body["forecast_kwh"] == 14
    assert datetime.fromisoformat(body["peak_timestamp"]) == first_timestamp + timedelta(hours=6)
