"""FastAPI production-model lifecycle tests independent of PostgreSQL."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.main as main
from app.ml.model_manager import get_model_manager
from ml_test_utils import MANIFEST


@pytest.mark.asyncio
async def test_lifespan_loads_once_before_database_and_releases(
    monkeypatch,
    caplog,
):
    manager = get_model_manager()
    manager.clear()
    monkeypatch.setattr(
        main.settings,
        "production_model_manifest",
        str(MANIFEST),
    )

    connection = MagicMock()
    connection.execute = AsyncMock()
    begin_context = MagicMock()
    begin_context.__aenter__ = AsyncMock(return_value=connection)
    begin_context.__aexit__ = AsyncMock(return_value=None)
    fake_engine = MagicMock()
    fake_engine.connect.return_value = begin_context
    fake_engine.dispose = AsyncMock()
    monkeypatch.setattr(main, "engine", fake_engine)

    with caplog.at_level(logging.INFO):
        async with main.lifespan(main.app):
            assert manager.load_count == 1
            assert main.app.state.production_model_manager is manager
            assert main.app.state.production_model.metadata["version"] == "v1.0.0"
            connection.execute.assert_awaited_once()

    assert manager.readiness().model_loaded is False
    fake_engine.dispose.assert_awaited_once()
    assert "Production model v1.0.0 loaded successfully" in caplog.text
