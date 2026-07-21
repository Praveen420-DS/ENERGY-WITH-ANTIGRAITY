from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.model_repository import ModelRepository
from app.schemas.model_registry import ModelInfoRead


class ModelRegistryService:
    @staticmethod
    async def get_models(db: AsyncSession) -> list[ModelInfoRead]:
        models = await ModelRepository.list_all(db)
        return [ModelInfoRead.model_validate(item) for item in models]
