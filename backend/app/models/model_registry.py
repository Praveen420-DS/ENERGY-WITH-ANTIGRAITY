from pydantic import BaseModel
from datetime import datetime

class ModelInfo(BaseModel):
    name: str
    version: str
    created_at: datetime
    metrics: dict
