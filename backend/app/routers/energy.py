from fastapi import APIRouter, Depends
from app.dependencies import get_current_user

router = APIRouter()

@router.get("/summary")
async def energy_summary(current_user=Depends(get_current_user)):
    return {"summary": {}}
