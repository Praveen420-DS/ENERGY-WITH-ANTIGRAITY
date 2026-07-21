from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anomaly import Anomaly


class AnomalyRepository:
    @staticmethod
    async def list_all(db: AsyncSession, limit: int = 100) -> list[Anomaly]:
        result = await db.execute(
            select(Anomaly).order_by(Anomaly.timestamp.desc()).limit(limit)
        )
        return list(result.scalars().all())
