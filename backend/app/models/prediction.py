from pydantic import BaseModel
from datetime import datetime

class PredictionRequest(BaseModel):
    meter_id: str
    horizon_hours: int

class PredictionResponse(BaseModel):
    meter_id: str
    timestamp: datetime
    predicted_kwh: float
    confidence: float
