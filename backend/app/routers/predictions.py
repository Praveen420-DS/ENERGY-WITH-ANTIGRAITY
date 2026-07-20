from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/")
async def list_predictions(current_user=Depends(get_current_user)):
    return {"predictions": []}
