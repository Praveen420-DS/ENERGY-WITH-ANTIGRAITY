def test_list_predictions(client, auth_headers):
    response = client.get("/api/predictions/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_prediction_repository_stores_actual_and_predicted_values():
    import asyncio
    from datetime import datetime
    from unittest.mock import AsyncMock, Mock

    from app.repositories.prediction_repository import PredictionRepository

    db = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    async def create_prediction():
        return await PredictionRepository.create(
            db,
            meter_id=1,
            model_id=1,
            horizon="hourly",
            target_start=datetime(2026, 9, 30),
            predicted_kwh=180.2,
            actual_kwh=174.3,
        )

    prediction = asyncio.run(create_prediction())

    assert prediction.actual_kwh == 174.3
    assert prediction.predicted_kwh == 180.2
    db.flush.assert_awaited_once()


def test_prediction_history_api_returns_actual_reading_and_null(monkeypatch):
    from datetime import datetime
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.dependencies import get_current_user
    from app.main import app
    from app.repositories.prediction_repository import PredictionRepository

    async def fake_db():
        yield object()

    rows = [
        SimpleNamespace(
            id=2,
            meter_id=1,
            horizon="hourly",
            predicted_at=datetime(2026, 9, 30, 12),
            target_start=datetime(2026, 9, 30, 13),
            predicted_kwh=163.704,
            actual_kwh=500.0,
            confidence=0.0,
        ),
        SimpleNamespace(
            id=1,
            meter_id=1,
            horizon="hourly",
            predicted_at=datetime(2026, 9, 30, 11),
            target_start=datetime(2026, 9, 30, 12),
            predicted_kwh=174.3,
            actual_kwh=None,
            confidence=0.0,
        ),
    ]

    async def fake_list_all(db, limit=100):
        return rows

    monkeypatch.setitem(app.dependency_overrides, get_db, fake_db)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: object())
    monkeypatch.setattr(
        PredictionRepository,
        "list_all",
        staticmethod(fake_list_all),
    )

    response = TestClient(app).get("/api/predictions/")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["actual_kwh"] == 500.0
    assert body[0]["predicted_kwh"] == 163.704
    assert body[1]["actual_kwh"] is None
