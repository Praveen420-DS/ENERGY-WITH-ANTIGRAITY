from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.energy_repository import EnergyRepository
from app.schemas.energy import EnergyRecordCreate, EnergyRecordRead, EnergySummary


class EnergyService:
    @staticmethod
    async def fetch_summary(db: AsyncSession) -> EnergySummary:
        summary = await EnergyRepository.get_summary(db)
        return EnergySummary(**summary)

    @staticmethod
    async def list_records(db: AsyncSession) -> list[EnergyRecordRead]:
        records = await EnergyRepository.list_records(db)
        return [EnergyRecordRead.model_validate(record) for record in records]

    @staticmethod
    async def create_record(
        db: AsyncSession, record: EnergyRecordCreate
    ) -> EnergyRecordRead:
        db_record = await EnergyRepository.create(db, record)
        return EnergyRecordRead.model_validate(db_record)
