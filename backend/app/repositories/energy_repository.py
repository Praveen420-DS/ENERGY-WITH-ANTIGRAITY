from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import EnergyRecord
from app.schemas.energy import EnergyRecordCreate


class EnergyRepository:
    @staticmethod
    async def list_records(db: AsyncSession, limit: int = 100) -> list[EnergyRecord]:
        result = await db.execute(
            select(EnergyRecord).order_by(EnergyRecord.timestamp.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, record: EnergyRecordCreate) -> EnergyRecord:
        db_record = EnergyRecord(
            meter_id=record.meter_id,
            consumption_kwh=record.consumption_kwh,
            voltage=record.voltage,
            current=record.current,
            power=record.power,
            power_factor=record.power_factor,
        )
        if record.timestamp is not None:
            db_record.timestamp = record.timestamp
        db.add(db_record)
        await db.flush()
        await db.refresh(db_record)
        return db_record

    @staticmethod
    async def get_summary(db: AsyncSession) -> dict:
        result = await db.execute(
            select(
                func.count(EnergyRecord.id),
                func.coalesce(func.sum(EnergyRecord.consumption_kwh), 0.0),
                func.coalesce(func.avg(EnergyRecord.consumption_kwh), 0.0),
            )
        )
        total_records, total_consumption, average_consumption = result.one()
        return {
            "total_records": int(total_records),
            "total_consumption_kwh": float(total_consumption),
            "average_consumption_kwh": float(average_consumption),
        }
