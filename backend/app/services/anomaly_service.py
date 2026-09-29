from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.energy_repository import EnergyRepository
from app.models.anomaly import Anomaly
from app.schemas.anomaly import AnomalyRead
from app.schemas.anomaly import AnomalyDetectionResult
from ml_service.models.anomaly_detector import AnomalyDetector


class AnomalyService:
    @staticmethod
    async def detect_anomalies(db: AsyncSession, meter_id: int | None, limit: int, threshold: float) -> AnomalyDetectionResult:
        history = await EnergyRepository.list_valid_history(db, meter_id, limit)
        detected = AnomalyDetector().detect(
            ({"meter_id": row.meter_id, "timestamp": row.timestamp,
              "consumption_kwh": row.consumption_kwh} for row in history), threshold
        )
        persisted = await AnomalyRepository.create_many(db, [Anomaly(**row) for row in detected])
        return AnomalyDetectionResult(
            examined_records=len(history), detected_count=len(persisted),
            anomalies=[AnomalyRead.model_validate(row) for row in persisted],
        )

    @staticmethod
    async def get_anomalies(db: AsyncSession) -> list[AnomalyRead]:
        anomalies = await AnomalyRepository.list_all(db)
        return [AnomalyRead.model_validate(item) for item in anomalies]
