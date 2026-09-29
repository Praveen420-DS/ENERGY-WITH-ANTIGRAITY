from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnomalyDetectionRequest(BaseModel):
    meter_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=5000, ge=3, le=20000)
    threshold: float = Field(default=3.5, gt=0, le=10)


class AnomalyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meter_id: int
    timestamp: datetime
    anomaly_type: str
    severity: str
    actual_kwh: float
    expected_kwh: float
    deviation_pct: float
    description: str | None
    is_resolved: bool


class AnomalyDetectionResult(BaseModel):
    examined_records: int
    detected_count: int
    anomalies: list[AnomalyRead]
