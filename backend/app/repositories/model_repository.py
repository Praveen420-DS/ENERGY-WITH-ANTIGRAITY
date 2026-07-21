from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_registry import MLModel


class ModelRepository:
    @staticmethod
    async def list_all(db: AsyncSession) -> list[MLModel]:
        result = await db.execute(select(MLModel).order_by(MLModel.created_at.desc()))
        return list(result.scalars().all())
