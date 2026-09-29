from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.anomaly import AnomalyDetectionRequest, AnomalyDetectionResult, AnomalyRead
from app.services.anomaly_service import AnomalyService

router = APIRouter()


@router.get("/", response_model=list[AnomalyRead])
async def list_anomalies(
    db: DbSession, current_user: User = Depends(get_current_user)
):
    return await AnomalyService.get_anomalies(db)


@router.post("/detect", response_model=AnomalyDetectionResult)
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    db: DbSession,
    current_user: User = Depends(get_current_user),
):
    return await AnomalyService.detect_anomalies(
        db, request.meter_id, request.limit, request.threshold
    )
