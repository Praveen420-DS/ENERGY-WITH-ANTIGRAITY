"""Authenticated production prediction and public readiness routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool

from app.dependencies import DbSession, get_current_user
from app.ml.model_manager import get_model_manager
from app.models.user import User
from app.schemas.prediction import (
    ErrorBody,
    ErrorResponse,
    ModelReadinessResponse,
    PredictionRead,
    ProductionPredictionRequest,
    ProductionPredictionResponse,
)
from app.services.prediction_service import (
    InvalidPredictionInputError,
    ModelNotReadyError,
    PredictionProcessingError,
    PredictionService,
)

LOGGER = logging.getLogger(__name__)
router = APIRouter()


def _error(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> HTTPException:
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=request_id,
            timestamp=datetime.now(timezone.utc),
        )
    )
    return HTTPException(status_code=status_code, detail=body.model_dump(mode="json"))


@router.get("/health", response_model=ModelReadinessResponse)
async def prediction_health(response: Response) -> ModelReadinessResponse:
    """Report model readiness independently from application liveness."""
    readiness = get_model_manager().readiness()
    if not readiness.model_loaded:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    LOGGER.debug("Model readiness checked status=%s", readiness.status)
    return ModelReadinessResponse(**readiness.__dict__)


@router.post(
    "/",
    response_model=ProductionPredictionResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"description": "Authentication required"},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_prediction(
    prediction_request: ProductionPredictionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ProductionPredictionResponse:
    """Generate one production prediction for an authenticated user."""
    del current_user
    request_id = request.state.request_id
    try:
        return await run_in_threadpool(
            PredictionService.predict,
            prediction_request,
            get_model_manager(),
            request_id,
        )
    except InvalidPredictionInputError as exc:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_PREDICTION_INPUT",
            str(exc),
            request_id,
        ) from exc
    except ModelNotReadyError as exc:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "MODEL_NOT_READY",
            "The production prediction model is unavailable.",
            request_id,
        ) from exc
    except PredictionProcessingError as exc:
        raise _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "PREDICTION_PROCESSING_ERROR",
            "The prediction could not be completed.",
            request_id,
        ) from exc


@router.get("/", response_model=list[PredictionRead])
async def list_predictions(
    db: DbSession,
    current_user: User = Depends(get_current_user),
) -> list[PredictionRead]:
    """Return authenticated persisted prediction history."""
    del current_user
    return await PredictionService.get_predictions(db)
