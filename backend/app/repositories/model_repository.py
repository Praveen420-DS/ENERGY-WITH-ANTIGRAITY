from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_registry import MLModel


class ModelRepository:
    @staticmethod
    async def list_all(db: AsyncSession) -> list[MLModel]:
        result = await db.execute(
            select(MLModel).order_by(MLModel.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_production_by_version(
        db: AsyncSession,
        version: str,
    ) -> MLModel | None:
        result = await db.execute(
            select(MLModel).where(
                MLModel.version == version,
                MLModel.status == "production",
            )
        )
        return result.scalar_one_or_none()