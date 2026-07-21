from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.model_registry import ModelInfoRead
from app.services.model_registry_service import ModelRegistryService

router = APIRouter()


@router.get("/", response_model=list[ModelInfoRead])
async def get_models(db: DbSession, current_user: User = Depends(get_current_user)):
    return await ModelRegistryService.get_models(db)
