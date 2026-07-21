from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import DbSession
from app.schemas.user import TokenResponse, UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=201)
async def register_user(user: UserCreate, db: DbSession):
    return await AuthService.register_user(db, user)


@router.post("/login", response_model=TokenResponse)
async def login_user(
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    return await AuthService.login(db, form_data.username, form_data.password)
