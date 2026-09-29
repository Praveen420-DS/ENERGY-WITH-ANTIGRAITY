from fastapi import APIRouter
from sqlalchemy import text
from app.services.system_service import SystemService

from app.database import engine

router = APIRouter()


@router.get("/health")
async def health_check():
    return await SystemService.health_check()
