from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelInfoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    version: str
    algorithm: str
    horizon: str
    status: str
    metrics: dict
    trained_at: datetime | None
    created_at: datetime
