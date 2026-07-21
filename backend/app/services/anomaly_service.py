from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.anomaly_repository import AnomalyRepository
from app.schemas.anomaly import AnomalyRead


class AnomalyService:
    @staticmethod
    async def get_anomalies(db: AsyncSession) -> list[AnomalyRead]:
        anomalies = await AnomalyRepository.list_all(db)
        return [AnomalyRead.model_validate(item) for item in anomalies]
