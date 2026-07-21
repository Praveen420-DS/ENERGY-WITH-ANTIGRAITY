from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.meter import MeterCreate, MeterRead
from app.services.meter_service import MeterService

router = APIRouter()


@router.get("/", response_model=list[MeterRead])
async def get_meters(db: DbSession, current_user: User = Depends(get_current_user)):
    return await MeterService.list_meters(db)


@router.post("/", response_model=MeterRead, status_code=201)
async def create_meter(
    meter: MeterCreate,
    db: DbSession,
    current_user: User = Depends(get_current_user),
):
    return await MeterService.create_meter(db, meter, owner_id=current_user.id)
