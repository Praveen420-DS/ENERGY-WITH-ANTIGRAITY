from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRead


class UserService:
    @staticmethod
    async def get_users(db: AsyncSession) -> list[UserRead]:
        users = await UserRepository.list_all(db)
        return [UserRead.model_validate(user) for user in users]
