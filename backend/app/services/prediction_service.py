"""Application service for persisted and production predictions."""

from __future__ import annotations

import logging
import math
from time import perf_counter
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.model_manager import (
    ProductionModelManager,
    ProductionModelManagerError,
)
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import (
    PredictionRead,
    ProductionPredictionRequest,
    ProductionPredictionResponse,
)
from ml_service.inference import (
    InputValidationError,
    ModelLoadingError,
    PredictionError,
    predict_one,
)

LOGGER = logging.getLogger(__name__)
UNIT_NOTE = (
    "Units depend on meter type: electricity, chilled water, steam, "
    "and hot water use different meter-reading units."
)


class PredictionServiceError(RuntimeError):
    """Base error for safe API mapping."""


class InvalidPredictionInputError(PredictionServiceError):
    """Inference rejected the validated application input."""


class ModelNotReadyError(PredictionServiceError):
    """Production inference is unavailable."""


class PredictionProcessingError(PredictionServiceError):
    """Production inference could not complete safely."""


class PredictionService:
    """Coordinate API inputs with the shared production inference runtime."""

    @staticmethod
    async def get_predictions(db: AsyncSession) -> list[PredictionRead]:
        """Return existing persisted prediction history."""
        predictions = await PredictionRepository.list_all(db)
        return [PredictionRead.model_validate(item) for item in predictions]

    @staticmethod
    def predict(
        request: ProductionPredictionRequest,
        manager: ProductionModelManager,
        request_id: str | None = None,
    ) -> ProductionPredictionResponse:
        """Generate one timed production prediction without retraining."""
        identifier = request_id or str(uuid4())
        started = perf_counter()
        LOGGER.info("Prediction request started request_id=%s", identifier)

        try:
            manifest_path = manager.manifest_path
            result = predict_one(
                request.to_inference_record(),
                manifest_path=manifest_path,
            )
        except InputValidationError as exc:
            LOGGER.info(
                "Prediction input rejected request_id=%s category=validation",
                identifier,
            )
            raise InvalidPredictionInputError(str(exc)) from exc
        except (ProductionModelManagerError, ModelLoadingError) as exc:
            LOGGER.error(
                "Prediction unavailable request_id=%s category=model_not_ready",
                identifier,
            )
            raise ModelNotReadyError("Production model is not ready.") from exc
        except PredictionError as exc:
            LOGGER.error(
                "Prediction failed request_id=%s category=inference",
                identifier,
            )
            raise PredictionProcessingError(
                "Production prediction could not be completed."
            ) from exc
        except Exception as exc:
            LOGGER.exception(
                "Unexpected prediction failure request_id=%s", identifier
            )
            raise PredictionProcessingError(
                "Production prediction could not be completed."
            ) from exc

        prediction = float(max(0.0, result["predicted_meter_reading"]))
        if not math.isfinite(prediction):
            raise PredictionProcessingError(
                "Production inference returned an invalid result."
            )
        elapsed_ms = (perf_counter() - started) * 1000
        warnings = list(result.get("warnings", []))
        LOGGER.info(
            "Prediction completed request_id=%s processing_time_ms=%.3f "
            "warning_count=%d",
            identifier,
            elapsed_ms,
            len(warnings),
        )
        return ProductionPredictionResponse(
            predicted_meter_reading=prediction,
            model_version=str(result["model_version"]),
            prediction_timestamp=result["prediction_timestamp"],
            input_timestamp=request.timestamp,
            meter=request.meter,
            unit_note=UNIT_NOTE,
            warnings=warnings,
            request_id=identifier,
            processing_time_ms=elapsed_ms,
        )
