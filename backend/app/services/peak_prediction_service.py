from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.energy_repository import EnergyRepository
from app.schemas.peak import PeakPredictionResponse
from ml_service.pipelines.peak_prediction import PeakPredictor


class PeakPredictionService:
    @staticmethod
    async def predict(db: AsyncSession, meter_id: int, horizon_records: int, history_limit: int) -> PeakPredictionResponse:
        history = await EnergyRepository.list_meter_history(db, meter_id, history_limit)
        result = PeakPredictor().predict(
            ({"timestamp": row.timestamp, "consumption_kwh": row.consumption_kwh} for row in history),
            horizon_records,
        )
        return PeakPredictionResponse(
            meter_id=meter_id, generated_at=datetime.now(timezone.utc), **result
        )
