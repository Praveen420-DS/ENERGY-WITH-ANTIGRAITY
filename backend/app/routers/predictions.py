from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.prediction import PredictionRead
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.get("/", response_model=list[PredictionRead])
async def list_predictions(
    db: DbSession, current_user: User = Depends(get_current_user)
):
    return await PredictionService.get_predictions(db)
