from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.anomaly import AnomalyRead
from app.services.anomaly_service import AnomalyService

router = APIRouter()


@router.get("/", response_model=list[AnomalyRead])
async def list_anomalies(
    db: DbSession, current_user: User = Depends(get_current_user)
):
    return await AnomalyService.get_anomalies(db)
