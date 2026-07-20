from fastapi import APIRouter, Depends
from app.models.user import UserLogin, UserCreate
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/register")
async def register_user(user: UserCreate):
    return AuthService.register_user(user)

@router.post("/login")
async def login_user(credentials: UserLogin):
    return AuthService.login_user(credentials)
