from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate


class UserRepository:
    @staticmethod
    async def find_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def find_by_username(db: AsyncSession, username: str) -> User | None:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, user: UserCreate, hashed_password: str) -> User:
        username = user.username or user.email.split("@")[0]
        db_user = User(
            username=username,
            email=user.email,
            hashed_password=hashed_password,
            full_name=user.full_name,
        )
        db.add(db_user)
        await db.flush()
        await db.refresh(db_user)
        return db_user

    @staticmethod
    async def list_all(db: AsyncSession) -> list[User]:
        result = await db.execute(select(User).order_by(User.id))
        return list(result.scalars().all())
