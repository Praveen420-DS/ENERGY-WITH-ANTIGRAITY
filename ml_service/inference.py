"""Thread-safe, dataset-independent inference for the packaged energy model."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd

from scripts.week2_feature_engineering import create_features_for_inference

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "models" / "production" / "current.json"
RAW_FIELDS = [
    "building_id", "meter", "timestamp", "site_id", "primary_use",
    "square_feet", "year_built", "floor_count", "air_temperature",
    "cloud_coverage", "dew_temperature", "precip_depth_1_hr",
    "sea_level_pressure", "wind_direction", "wind_speed",
]
INTEGER_FIELDS = {"building_id", "meter", "site_id"}
NUMERIC_FIELDS = {
    "square_feet", "year_built", "floor_count", "air_temperature",
    "cloud_coverage", "dew_temperature", "precip_depth_1_hr",
    "sea_level_pressure", "wind_direction", "wind_speed",
}


class ProductionInferenceError(Exception):
    """Safe base exception for production inference failures."""


class InputValidationError(ProductionInferenceError):
    """Request does not satisfy the production input contract."""


class ModelLoadingError(ProductionInferenceError):
    """Production package is absent, corrupt, or incompatible."""


class PredictionError(ProductionInferenceError):
    """A validated request could not be predicted safely."""


@dataclass(frozen=True)
class LoadedProductionModel:
    pipeline: Any
    metadata: dict
    schema: dict
    package_dir: Path
    manifest: dict


_PREDICTION_LOCK = threading.RLock()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_manifest(path: str | Path | None) -> Path:
    manifest = Path(path) if path else DEFAULT_MANIFEST
    if not manifest.is_absolute():
        manifest = (PROJECT_ROOT / manifest).resolve()
    return manifest


def verify_package_checksums(package_dir: Path) -> dict:
    checksum_path = package_dir / "checksums.json"
    if not checksum_path.is_file():
        raise ModelLoadingError("Production package checksum manifest is missing.")
    checksums = json.loads(checksum_path.read_text(encoding="utf-8"))
    failures = []
    for relative, expected in checksums["package_files"].items():
        candidate = package_dir / relative
        if not candidate.is_file() or _sha256(candidate) != expected:
            failures.append(relative)
    for relative, expected in checksums.get("source_files", {}).items():
        candidate = PROJECT_ROOT / relative
        if not candidate.is_file() or _sha256(candidate) != expected:
            failures.append(relative)
    if failures:
        raise ModelLoadingError(f"Checksum verification failed for: {', '.join(failures)}")
    return checksums


@lru_cache(maxsize=4)
def _load_cached(manifest_string: str, manifest_mtime_ns: int) -> LoadedProductionModel:
    del manifest_mtime_ns
    manifest_path = Path(manifest_string)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_dir = (manifest_path.parent / manifest["version_directory"]).resolve()
        verify_package_checksums(package_dir)
        metadata = json.loads((package_dir / "model_metadata.json").read_text(encoding="utf-8"))
        schema = json.loads((package_dir / "feature_schema.json").read_text(encoding="utf-8"))
        pipeline = joblib.load(package_dir / manifest["model_path"])
    except ModelLoadingError:
        raise
    except Exception as exc:
        LOGGER.exception("Production model load failed")
        raise ModelLoadingError("Production model could not be loaded.") from exc
    expected = metadata["predictor_columns"]
    actual = list(getattr(pipeline, "feature_names_in_", []))
    if actual != expected:
        raise ModelLoadingError("Packaged pipeline feature contract does not match metadata.")
    LOGGER.info("Loaded production model version %s", metadata["version"])
    return LoadedProductionModel(pipeline, metadata, schema, package_dir, manifest)


def load_production_model(manifest_path: str | Path | None = None) -> LoadedProductionModel:
    """Load and cache the checksum-verified active package."""
    path = _resolve_manifest(manifest_path)
    if not path.is_file():
        raise ModelLoadingError(f"Production manifest not found: {path}")
    return _load_cached(str(path), path.stat().st_mtime_ns)


def _finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise InputValidationError(f"'{name}' must be numeric, not boolean.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InputValidationError(f"'{name}' must be numeric.") from exc
    if not math.isfinite(result):
        raise InputValidationError(f"'{name}' must be finite.")
    return result


def validate_prediction_input(record: Mapping[str, Any],
                              loaded: LoadedProductionModel | None = None) -> tuple[dict, list[str]]:
    """Validate one raw application record; return normalized values and warnings."""
    if not isinstance(record, Mapping):
        raise InputValidationError("Prediction input must be an object.")
    missing = sorted(set(RAW_FIELDS) - set(record))
    if missing:
        raise InputValidationError(f"Missing required fields: {missing}")
    if "meter_reading" in record:
        raise InputValidationError("'meter_reading' is a target and must not be supplied.")
    extra = sorted(set(record) - set(RAW_FIELDS))
    if extra:
        raise InputValidationError(f"Unexpected fields: {extra}")
    normalized = {}
    for name in INTEGER_FIELDS:
        value = _finite_number(name, record[name])
        if not value.is_integer():
            raise InputValidationError(f"'{name}' must be an integer.")
        normalized[name] = int(value)
    for name in NUMERIC_FIELDS:
        normalized[name] = _finite_number(name, record[name])
    if normalized["building_id"] < 0 or normalized["site_id"] < 0:
        raise InputValidationError("building_id and site_id must be nonnegative.")
    if normalized["meter"] not in {0, 1, 2, 3}:
        raise InputValidationError("'meter' must be one of 0, 1, 2, or 3.")
    if normalized["square_feet"] < 0:
        raise InputValidationError("'square_feet' must be nonnegative.")
    if not 1800 <= normalized["year_built"] <= 2016:
        raise InputValidationError("'year_built' must be between 1800 and 2016.")
    if normalized["floor_count"] <= 0:
        raise InputValidationError("'floor_count' must be greater than zero.")
    if not 0 <= normalized["wind_direction"] <= 360:
        raise InputValidationError("'wind_direction' must be between 0 and 360 degrees.")
    primary_use = record["primary_use"]
    if not isinstance(primary_use, str) or not primary_use.strip():
        raise InputValidationError("'primary_use' must be a non-empty string.")
    normalized["primary_use"] = primary_use.strip()
    try:
        timestamp = pd.Timestamp(record["timestamp"])
    except Exception as exc:
        raise InputValidationError("'timestamp' must be a valid ISO-8601 date-time.") from exc
    if pd.isna(timestamp) or timestamp.tzinfo is not None:
        raise InputValidationError("'timestamp' must be a timezone-naive ISO-8601 date-time.")
    if timestamp.year < 1900 or timestamp.year > 2100:
        raise InputValidationError("'timestamp' year must be between 1900 and 2100.")
    normalized["timestamp"] = timestamp
    warnings = []
    if loaded:
        known = set(loaded.metadata["known_categories"]["primary_use"])
        if normalized["primary_use"] not in known:
            warnings.append("Unknown primary_use encoded as all-zero one-hot values.")
        bounds = loaded.metadata["training_identifier_ranges"]
        if not bounds["building_id"]["min"] <= normalized["building_id"] <= bounds["building_id"]["max"]:
            warnings.append("Unseen building_id is accepted but excluded from model predictors.")
        if not bounds["site_id"]["min"] <= normalized["site_id"] <= bounds["site_id"]["max"]:
            warnings.append("Unseen site_id is accepted but excluded from model predictors.")
        if timestamp < pd.Timestamp(loaded.metadata["training_timestamp_range"]["min"]) or \
                timestamp > pd.Timestamp(loaded.metadata["training_timestamp_range"]["max"]):
            warnings.append("Timestamp is outside the training period; temporal drift risk is elevated.")
    return normalized, warnings


def build_feature_frame(records: Sequence[Mapping[str, Any]],
                        loaded: LoadedProductionModel) -> tuple[pd.DataFrame, list[list[str]]]:
    if isinstance(records, Mapping) or not isinstance(records, Sequence) or len(records) == 0:
        raise InputValidationError("Batch input must be a non-empty sequence of objects.")
    normalized, warnings = zip(*(validate_prediction_input(r, loaded) for r in records))
    raw = pd.DataFrame(normalized, columns=RAW_FIELDS)
    featured = create_features_for_inference(raw)
    predictors = loaded.metadata["predictor_columns"]
    missing = sorted(set(predictors) - set(featured))
    if missing:
        raise PredictionError(f"Feature engineering did not produce required fields: {missing}")
    aligned = featured.loc[:, predictors]
    if list(aligned.columns) != predictors:
        raise PredictionError("Feature alignment failed.")
    return aligned, list(warnings)


def predict_batch(records: Sequence[Mapping[str, Any]],
                  manifest_path: str | Path | None = None) -> list[dict]:
    loaded = load_production_model(manifest_path)
    features, warnings = build_feature_frame(records, loaded)
    try:
        with _PREDICTION_LOCK:
            raw_predictions = np.asarray(loaded.pipeline.predict(features), dtype=float)
    except Exception as exc:
        LOGGER.exception("Production prediction failed")
        raise PredictionError("Model prediction failed.") from exc
    if raw_predictions.shape != (len(records),) or not np.isfinite(raw_predictions).all():
        raise PredictionError("Model produced invalid prediction output.")
    clipped = np.maximum(raw_predictions, 0.0)
    generated = datetime.now(timezone.utc).isoformat()
    responses = []
    for record, prediction, was_clipped, item_warnings in zip(
            records, clipped, raw_predictions < 0, warnings):
        messages = list(item_warnings)
        if was_clipped:
            messages.append("Negative model output was clipped to zero.")
        responses.append({
            "predicted_meter_reading": float(prediction),
            "model_version": loaded.metadata["version"],
            "prediction_timestamp": generated,
            "input_timestamp": str(pd.Timestamp(record["timestamp"])),
            "warnings": messages,
            "units": "Meter-dependent; meter codes may represent electricity, chilled water, steam, or hot water.",
        })
    return responses


def predict_one(record: Mapping[str, Any],
                manifest_path: str | Path | None = None) -> dict:
    return predict_batch([record], manifest_path)[0]


def get_model_metadata(manifest_path: str | Path | None = None) -> dict:
    return dict(load_production_model(manifest_path).metadata)
