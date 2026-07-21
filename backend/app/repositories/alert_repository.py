from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertConfig
from app.schemas.alert import AlertConfigCreate


class AlertRepository:
    @staticmethod
    async def list_for_user(db: AsyncSession, user_id: int) -> list[AlertConfig]:
        result = await db.execute(
            select(AlertConfig)
            .where(AlertConfig.user_id == user_id)
            .order_by(AlertConfig.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        db: AsyncSession, alert: AlertConfigCreate, user_id: int
    ) -> AlertConfig:
        db_alert = AlertConfig(
            user_id=user_id,
            meter_id=alert.meter_id,
            threshold_kwh=alert.threshold_kwh,
            email_enabled=alert.email_enabled,
            sms_enabled=alert.sms_enabled,
        )
        db.add(db_alert)
        await db.flush()
        await db.refresh(db_alert)
        return db_alert
