from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/")
async def get_alerts(current_user=Depends(get_current_user)):
    return {"alerts": []}
