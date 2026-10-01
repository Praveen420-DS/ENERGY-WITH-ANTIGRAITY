from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction


class PredictionRepository:
    @staticmethod
    async def list_all(
        db: AsyncSession,
        limit: int = 100,
    ) -> list[Prediction]:
        result = await db.execute(
            select(Prediction)
            .order_by(Prediction.predicted_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        meter_id: int,
        model_id: int | None,
        horizon: str,
        target_start: datetime,
        predicted_kwh: float,
        actual_kwh: float | None = None,
        confidence: float = 0.0,
    ) -> Prediction:
        prediction = Prediction(
            meter_id=meter_id,
            model_id=model_id,
            horizon=horizon,
            target_start=target_start,
            predicted_kwh=predicted_kwh,
            actual_kwh=actual_kwh,
            confidence=confidence,
        )

        db.add(prediction)
        await db.flush()
        await db.refresh(prediction)

        return prediction
