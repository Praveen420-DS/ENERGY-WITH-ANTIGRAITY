from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserCreate, UserRead
from app.utils.security import create_access_token, hash_password, verify_password


class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, user: UserCreate) -> UserRead:
        existing = await UserRepository.find_by_email(db, user.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        username = user.username or user.email.split("@")[0]
        existing_username = await UserRepository.find_by_username(db, username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        hashed = hash_password(user.password)
        db_user = await UserRepository.create(db, user, hashed)
        return UserRead.model_validate(db_user)

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> TokenResponse:
        user = await UserRepository.find_by_email(db, email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )

        token = create_access_token({"sub": user.email})
        return TokenResponse(access_token=token)
