from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.alert import AlertConfigCreate, AlertConfigRead
from app.services.alert_service import AlertService

router = APIRouter()


@router.get("/", response_model=list[AlertConfigRead])
async def get_alerts(db: DbSession, current_user: User = Depends(get_current_user)):
    return await AlertService.get_alerts(db, current_user.id)


@router.post("/", response_model=AlertConfigRead, status_code=201)
async def create_alert(
    alert: AlertConfigCreate,
    db: DbSession,
    current_user: User = Depends(get_current_user),
):
    return await AlertService.create_alert(db, alert, current_user.id)
