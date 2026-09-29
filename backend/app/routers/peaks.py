from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.peak import PeakPredictionRequest, PeakPredictionResponse
from app.services.peak_prediction_service import PeakPredictionService

router = APIRouter()


@router.post("/predict", response_model=PeakPredictionResponse)
async def predict_peak(
    request: PeakPredictionRequest,
    db: DbSession,
    current_user: User = Depends(get_current_user),
):
    try:
        return await PeakPredictionService.predict(
            db, request.meter_id, request.horizon_records, request.history_limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
