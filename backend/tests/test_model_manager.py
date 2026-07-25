"""Production model-manager lifecycle tests."""

from pathlib import Path

import pytest

from app.ml.model_manager import (
    ProductionModelManager,
    ProductionModelManagerError,
)
from ml_test_utils import MANIFEST


def test_manifest_resolution_is_repository_controlled():
    manager = ProductionModelManager()
    assert manager.resolve_manifest(MANIFEST) == MANIFEST.resolve()

    with pytest.raises(ProductionModelManagerError, match="models/production"):
        manager.resolve_manifest(Path(__file__))


def test_model_loads_once_and_exposes_readiness():
    manager = ProductionModelManager()
    first = manager.load(MANIFEST)
    second = manager.load(MANIFEST)
    readiness = manager.readiness()

    assert first is second
    assert manager.load_count == 1
    assert manager.version == "v1.0.0"
    assert manager.metadata["algorithm"] == "RandomForestRegressor"
    assert readiness.status == "ready"
    assert readiness.model_loaded is True
    assert readiness.model_version == manager.version
    assert readiness.checksum_status == "verified"
    assert readiness.loaded_at is not None


def test_uninitialized_manager_is_not_ready():
    readiness = ProductionModelManager().readiness()
    assert readiness.status == "not_ready"
    assert readiness.model_loaded is False
    assert readiness.checksum_status == "not_verified"
