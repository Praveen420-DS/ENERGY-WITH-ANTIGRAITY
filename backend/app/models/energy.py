from pydantic import BaseModel
from datetime import datetime

class EnergyRecord(BaseModel):
    timestamp: datetime
    meter_id: str
    consumption_kwh: float
    production_kwh: float = 0.0
