from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.models.user import UserCreate
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/register")
async def register_user(user: UserCreate):
    return AuthService.register_user(user)

@router.post("/login")
async def login_user(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    return AuthService.login(
        form_data.username,
        form_data.password
    )