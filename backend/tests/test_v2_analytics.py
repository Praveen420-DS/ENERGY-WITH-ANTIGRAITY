from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.anomaly_service import AnomalyService
from app.services.peak_prediction_service import PeakPredictionService
from ml_service.models.anomaly_detector import AnomalyDetector
from ml_service.pipelines.peak_prediction import PeakPredictor


def test_mad_detector_finds_spike_per_meter():
    rows = [{"meter_id": 1, "timestamp": datetime(2025, 1, day, tzinfo=timezone.utc), "consumption_kwh": value}
            for day, value in enumerate([10, 10, 11, 9, 10, 100], 1)]
    found = AnomalyDetector().detect(rows)
    assert len(found) == 1
    assert found[0]["anomaly_type"] == "spike"
    assert found[0]["actual_kwh"] == 100


def test_mad_detector_skips_constant_history():
    rows = [{"meter_id": 1, "timestamp": datetime.now(timezone.utc), "consumption_kwh": 5} for _ in range(4)]
    assert AnomalyDetector().detect(rows) == []


def test_peak_predictor_requires_history_and_horizon_changes_future_peak():
    with pytest.raises(ValueError):
        PeakPredictor().predict([{"consumption_kwh": 1}] * 2)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    history = [{"timestamp": start + timedelta(hours=index), "consumption_kwh": value}
               for index, value in enumerate([2, 4, 6, 8])]
    one = PeakPredictor().predict(history, horizon=1)
    three = PeakPredictor().predict(history, horizon=3)
    assert one["forecast_kwh"] == pytest.approx(10)
    assert three["forecast_kwh"] == pytest.approx(14)
    assert one["peak_timestamp"] == start + timedelta(hours=4)
    assert three["peak_timestamp"] == start + timedelta(hours=6)
    assert three["horizon_records"] == 3
    assert three["history_records"] == 4


@pytest.mark.parametrize("horizon", [0, 25, 1.5])
def test_peak_predictor_rejects_invalid_horizon(horizon):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    history = [{"timestamp": start + timedelta(hours=index), "consumption_kwh": index + 1}
               for index in range(3)]
    with pytest.raises(ValueError, match="horizon"):
        PeakPredictor().predict(history, horizon=horizon)


def test_peak_predictor_rejects_invalid_observations():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    history = [{"timestamp": start + timedelta(hours=index), "consumption_kwh": value}
               for index, value in enumerate([1, float("nan"), 3])]
    with pytest.raises(ValueError, match="finite"):
        PeakPredictor().predict(history)


@pytest.mark.asyncio
async def test_anomaly_service_uses_observed_history_and_persists(monkeypatch):
    records = [SimpleNamespace(meter_id=1, timestamp=datetime.now(timezone.utc), consumption_kwh=value)
               for value in [10, 10, 9, 11, 10, 100]]
    monkeypatch.setattr("app.services.anomaly_service.EnergyRepository.list_valid_history", AsyncMock(return_value=records))
    stored = []
    async def create_many(db, anomalies):
        stored.extend(anomalies)
        for index, item in enumerate(anomalies, 1):
            item.id = index
            item.is_resolved = False
        return anomalies
    monkeypatch.setattr("app.services.anomaly_service.AnomalyRepository.create_many", create_many)
    result = await AnomalyService.detect_anomalies(object(), 1, 100, 3.5)
    assert result.examined_records == 6
    assert result.detected_count == 1
    assert result.anomalies[0].actual_kwh == 100


@pytest.mark.asyncio
async def test_peak_service_reads_meter_history_without_persistence(monkeypatch):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = [SimpleNamespace(timestamp=start + timedelta(hours=index), consumption_kwh=value)
            for index, value in enumerate([2, 4, 6])]
    fetch = AsyncMock(return_value=rows)
    monkeypatch.setattr("app.services.peak_prediction_service.EnergyRepository.list_meter_history", fetch)
    result = await PeakPredictionService.predict(object(), 4, 1, 100)
    fetch.assert_awaited_once()
    assert result.meter_id == 4
    assert result.forecast_kwh == 8
    assert result.peak_timestamp == start + timedelta(hours=3)
