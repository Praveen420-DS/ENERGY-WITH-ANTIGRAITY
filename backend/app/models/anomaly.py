from pydantic import BaseModel
from datetime import datetime

class AnomalyRecord(BaseModel):
    timestamp: datetime
    meter_id: str
    value: float
    score: float
    description: str
