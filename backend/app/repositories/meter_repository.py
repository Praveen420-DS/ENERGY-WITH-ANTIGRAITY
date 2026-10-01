from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meter import Meter
from app.schemas.meter import MeterCreate


class MeterRepository:
    @staticmethod
    async def list_all(db: AsyncSession) -> list[Meter]:
        result = await db.execute(select(Meter).order_by(Meter.id))
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession,
        meter: MeterCreate,
        owner_id: int | None = None,
    ) -> Meter:
        db_meter = Meter(
            meter_id=meter.meter_id,
            name=meter.name,
            location=meter.location,
            capacity_kw=meter.capacity_kw,
            meter_type=meter.meter_type,
            owner_id=owner_id,
        )
        db.add(db_meter)
        await db.flush()
        await db.refresh(db_meter)
        return db_meter

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        meter_id: int,
    ) -> Meter | None:
        result = await db.execute(
            select(Meter).where(Meter.id == meter_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_meter_identifier(
        db: AsyncSession,
        meter_identifier: str,
    ) -> Meter | None:
        result = await db.execute(
            select(Meter).where(Meter.meter_id == meter_identifier)
        )
        return result.scalar_one_or_none()