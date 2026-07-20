from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/")
async def list_anomalies(current_user=Depends(get_current_user)):
    return {"anomalies": []}
