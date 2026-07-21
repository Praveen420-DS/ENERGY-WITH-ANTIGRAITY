from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction


class PredictionRepository:
    @staticmethod
    async def list_all(db: AsyncSession, limit: int = 100) -> list[Prediction]:
        result = await db.execute(
            select(Prediction).order_by(Prediction.predicted_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
