"""Process-level lifecycle manager for the trusted production model package."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from ml_service.inference import (
    PROJECT_ROOT,
    LoadedProductionModel,
    ModelLoadingError,
    load_production_model,
)

LOGGER = logging.getLogger(__name__)
PRODUCTION_ROOT = (PROJECT_ROOT / "models" / "production").resolve()
REQUIRED_PACKAGE_FILES = frozenset(
    {
        "model.joblib",
        "feature_schema.json",
        "model_metadata.json",
        "checksums.json",
    }
)


class ProductionModelManagerError(RuntimeError):
    """The trusted production model package could not be initialized."""


@dataclass(frozen=True)
class ModelReadiness:
    """Safe model-readiness information suitable for API responses."""

    status: str
    model_loaded: bool
    model_version: str | None
    algorithm: str | None
    schema_version: str | None
    loaded_at: datetime | None
    checksum_status: str


class ProductionModelManager:
    """Load and expose one immutable production inference runtime per process."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._loaded: LoadedProductionModel | None = None
        self._manifest_path: Path | None = None
        self._loaded_at: datetime | None = None
        self._load_count = 0
        self._last_error: str | None = None

    @staticmethod
    def resolve_manifest(manifest_path: str | Path) -> Path:
        """Resolve a repository-controlled production manifest safely."""
        candidate = Path(manifest_path)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(PRODUCTION_ROOT)
        except ValueError as exc:
            raise ProductionModelManagerError(
                "Production manifest must be inside models/production."
            ) from exc
        if resolved.name != "current.json":
            raise ProductionModelManagerError(
                "Production manifest must resolve to current.json."
            )
        return resolved

    @staticmethod
    def _validate_required_files(loaded: LoadedProductionModel) -> None:
        try:
            loaded.package_dir.resolve().relative_to(PRODUCTION_ROOT)
        except ValueError as exc:
            raise ProductionModelManagerError(
                "Active production package resolves outside models/production."
            ) from exc
        missing = sorted(
            name
            for name in REQUIRED_PACKAGE_FILES
            if not (loaded.package_dir / name).is_file()
        )
        if missing:
            raise ProductionModelManagerError(
                "Production package is missing required files: "
                + ", ".join(missing)
            )

    def load(self, manifest_path: str | Path) -> LoadedProductionModel:
        """Load the active package once and return the shared runtime."""
        resolved_manifest = self.resolve_manifest(manifest_path)
        with self._lock:
            if self._loaded is not None:
                if resolved_manifest != self._manifest_path:
                    raise ProductionModelManagerError(
                        "Production model is already loaded from another manifest."
                    )
                return self._loaded

            LOGGER.info("Loading production model from active manifest")
            try:
                loaded = load_production_model(resolved_manifest)
                self._validate_required_files(loaded)
            except (ModelLoadingError, ProductionModelManagerError) as exc:
                self._last_error = str(exc)
                LOGGER.exception("Production model loading failed")
                raise ProductionModelManagerError(
                    "Production model package could not be loaded."
                ) from exc
            except Exception as exc:
                self._last_error = type(exc).__name__
                LOGGER.exception("Unexpected production model loading failure")
                raise ProductionModelManagerError(
                    "Unexpected production model loading failure."
                ) from exc

            self._loaded = loaded
            self._manifest_path = resolved_manifest
            self._loaded_at = datetime.now(timezone.utc)
            self._load_count += 1
            self._last_error = None
            LOGGER.info(
                "Production model %s loaded successfully",
                loaded.metadata["version"],
            )
            return loaded

    @property
    def loaded_model(self) -> LoadedProductionModel:
        """Return the initialized runtime or fail with a safe readiness error."""
        if self._loaded is None:
            raise ProductionModelManagerError("Production model is not ready.")
        return self._loaded

    @property
    def manifest_path(self) -> Path:
        """Return the resolved manifest used by the initialized runtime."""
        if self._manifest_path is None:
            raise ProductionModelManagerError("Production model is not ready.")
        return self._manifest_path

    @property
    def metadata(self) -> dict[str, Any]:
        """Return a defensive copy of safe model metadata."""
        return dict(self.loaded_model.metadata)

    @property
    def version(self) -> str:
        """Return the active version from model metadata."""
        return str(self.loaded_model.metadata["version"])

    @property
    def load_count(self) -> int:
        """Return successful physical initialization count for this process."""
        return self._load_count

    def readiness(self) -> ModelReadiness:
        """Return readiness without exposing local paths or exception details."""
        loaded = self._loaded
        metadata = loaded.metadata if loaded else {}
        return ModelReadiness(
            status="ready" if loaded else "not_ready",
            model_loaded=loaded is not None,
            model_version=metadata.get("version"),
            algorithm=metadata.get("algorithm"),
            schema_version=(
                loaded.schema.get("schema_version") if loaded else None
            ),
            loaded_at=self._loaded_at,
            checksum_status="verified" if loaded else "not_verified",
        )

    def clear(self) -> None:
        """Release process references during application shutdown."""
        with self._lock:
            self._loaded = None
            self._manifest_path = None
            self._loaded_at = None


MODEL_MANAGER = ProductionModelManager()


def get_model_manager() -> ProductionModelManager:
    """Return the process-level production model manager."""
    return MODEL_MANAGER
