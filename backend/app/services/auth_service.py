"""Registration and login services."""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserCreate, UserRead
from app.utils.security import create_access_token, hash_password, verify_password

LOGGER = logging.getLogger(__name__)
GENERIC_LOGIN_ERROR = "Incorrect email or password"


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
    async def login(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> TokenResponse:
        normalized_email = email.strip().lower()
        user = await UserRepository.find_by_email(db, normalized_email)
        if user is None:
            LOGGER.warning("Authentication failed reason=user_not_found")
            raise AuthService._generic_login_failure()
        if len(password.encode("utf-8")) > 72:
            LOGGER.warning("Authentication failed reason=malformed_password")
            raise AuthService._generic_login_failure()
        if not verify_password(password, user.hashed_password):
            LOGGER.warning("Authentication failed reason=password_mismatch")
            raise AuthService._generic_login_failure()
        if not user.is_active:
            LOGGER.warning("Authentication failed reason=inactive_user")
            raise AuthService._generic_login_failure()

        token = create_access_token({"sub": user.email})
        return TokenResponse(access_token=token)

    @staticmethod
    def _generic_login_failure() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )
