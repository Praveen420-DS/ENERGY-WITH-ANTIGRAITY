from fastapi import APIRouter, Depends

from app.dependencies import DbSession, get_current_user
from app.models.user import User
from app.schemas.user import UserRead
from app.services.user_service import UserService

router = APIRouter()


@router.get("/", response_model=list[UserRead])
async def list_users(db: DbSession, current_user: User = Depends(get_current_user)):
    return await UserService.get_users(db)
