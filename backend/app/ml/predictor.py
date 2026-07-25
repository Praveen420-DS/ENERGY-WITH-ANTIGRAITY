"""Backend prediction adapter for the production inference service."""

from __future__ import annotations

from typing import Any, Mapping

from ml_service.inference import predict_one


def predict(processed_features: Mapping[str, Any]) -> float:
    """Predict energy consumption from a processed application record.

    Feature engineering, feature alignment, model invocation, and inference
    validation remain owned by :mod:`ml_service.inference`.

    Args:
        processed_features: Validated application features accepted by the
            production inference contract.

    Returns:
        The nonnegative predicted meter reading as a Python ``float``.
    """
    result = predict_one(processed_features)
    return float(max(0.0, result["predicted_meter_reading"]))
