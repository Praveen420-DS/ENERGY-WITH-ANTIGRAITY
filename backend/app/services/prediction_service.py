from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction import PredictionRead


class PredictionService:
    @staticmethod
    async def get_predictions(db: AsyncSession) -> list[PredictionRead]:
        predictions = await PredictionRepository.list_all(db)
        return [PredictionRead.model_validate(item) for item in predictions]
