from datetime import datetime

from pydantic import BaseModel, Field


class PeakPredictionRequest(BaseModel):
    meter_id: int = Field(ge=1)
    horizon_records: int = Field(default=1, ge=1, le=24)
    history_limit: int = Field(default=500, ge=3, le=5000)


class PeakPredictionResponse(BaseModel):
    meter_id: int
    generated_at: datetime
    peak_timestamp: datetime
    forecast_kwh: float
    peak_threshold_kwh: float
    baseline_kwh: float
    is_peak_likely: bool
    horizon_records: int
    history_records: int
