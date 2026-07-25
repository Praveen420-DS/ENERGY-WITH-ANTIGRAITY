"""Compatibility loading adapter backed by the production model manager."""

from __future__ import annotations

from pathlib import Path

from ml_service.inference import LoadedProductionModel

from app.ml.model_manager import (
    ProductionModelManagerError,
    get_model_manager,
)

ProductionModelLoadError = ProductionModelManagerError


def load_model(
    manifest_path: str | Path = "models/production/current.json",
) -> LoadedProductionModel:
    """Load the active package through the process-level model manager."""
    return get_model_manager().load(manifest_path)


def cache_clear() -> None:
    """Release manager references; retained for test compatibility."""
    get_model_manager().clear()


load_model.cache_clear = cache_clear  # type: ignore[attr-defined]
