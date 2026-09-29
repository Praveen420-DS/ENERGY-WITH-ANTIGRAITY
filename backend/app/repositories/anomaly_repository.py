from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models.anomaly import Anomaly


class AnomalyRepository:
    @staticmethod
    async def create_many(db: AsyncSession, anomalies: list[Anomaly]) -> list[Anomaly]:
        persisted: list[Anomaly] = []
        seen: set[tuple[int, datetime]] = set()
        for anomaly in anomalies:
            identity = (anomaly.meter_id, anomaly.timestamp)
            if identity in seen:
                continue
            seen.add(identity)
            values = {
                column.key: getattr(anomaly, column.key)
                for column in Anomaly.__table__.columns
                if column.key != "id" and getattr(anomaly, column.key, None) is not None
            }
            statement = (
                insert(Anomaly)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["meter_id", "timestamp"])
                .returning(Anomaly)
            )
            inserted = (await db.execute(statement)).scalars().first()
            if inserted is not None:
                persisted.append(inserted)
                continue

            existing = await db.execute(
                select(Anomaly).where(
                    Anomaly.meter_id == anomaly.meter_id,
                    Anomaly.timestamp == anomaly.timestamp,
                )
            )
            persisted.append(existing.scalar_one())
        return persisted

    @staticmethod
    async def list_all(db: AsyncSession, limit: int = 100) -> list[Anomaly]:
        result = await db.execute(
            select(Anomaly).order_by(Anomaly.timestamp.desc()).limit(limit)
        )
        return list(result.scalars().all())
