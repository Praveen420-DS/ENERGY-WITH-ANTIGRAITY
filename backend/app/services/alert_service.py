from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertConfigCreate, AlertConfigRead


class AlertService:
    @staticmethod
    async def get_alerts(db: AsyncSession, user_id: int) -> list[AlertConfigRead]:
        alerts = await AlertRepository.list_for_user(db, user_id)
        return [AlertConfigRead.model_validate(item) for item in alerts]

    @staticmethod
    async def create_alert(
        db: AsyncSession, alert: AlertConfigCreate, user_id: int
    ) -> AlertConfigRead:
        db_alert = await AlertRepository.create(db, alert, user_id)
        return AlertConfigRead.model_validate(db_alert)
