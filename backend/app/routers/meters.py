from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/")
async def get_meters(current_user=Depends(get_current_user)):
    return {"meters": []}
