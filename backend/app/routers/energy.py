from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.energy import EnergyRecordCreate, EnergyRecordRead, EnergySummary
from app.services.energy_service import EnergyService

router = APIRouter()


@router.get("/summary", response_model=EnergySummary)
async def energy_summary(db: DbSession, current_user: User = Depends(get_current_user)):
    return await EnergyService.fetch_summary(db)


@router.get("/records", response_model=list[EnergyRecordRead])
async def list_energy_records(
    db: DbSession, current_user: User = Depends(get_current_user)
):
    return await EnergyService.list_records(db)


@router.post("/records", response_model=EnergyRecordRead, status_code=201)
async def create_energy_record(
    record: EnergyRecordCreate,
    db: DbSession,
    current_user: User = Depends(get_current_user),
):
    return await EnergyService.create_record(db, record)
