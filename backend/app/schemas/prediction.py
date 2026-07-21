from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PredictionRequest(BaseModel):
    meter_id: int
    horizon_hours: int = Field(ge=1, le=168)


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meter_id: int
    horizon: str
    predicted_at: datetime
    target_start: datetime
    predicted_kwh: float
    confidence: float
