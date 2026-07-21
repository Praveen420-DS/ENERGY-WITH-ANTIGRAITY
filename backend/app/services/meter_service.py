from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.meter_repository import MeterRepository
from app.schemas.meter import MeterCreate, MeterRead


class MeterService:
    @staticmethod
    async def list_meters(db: AsyncSession) -> list[MeterRead]:
        meters = await MeterRepository.list_all(db)
        return [MeterRead.model_validate(meter) for meter in meters]

    @staticmethod
    async def create_meter(
        db: AsyncSession, meter: MeterCreate, owner_id: int | None = None
    ) -> MeterRead:
        db_meter = await MeterRepository.create(db, meter, owner_id=owner_id)
        return MeterRead.model_validate(db_meter)
