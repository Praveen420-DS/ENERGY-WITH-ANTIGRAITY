from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
