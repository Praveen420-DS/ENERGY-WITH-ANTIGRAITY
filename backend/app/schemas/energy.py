from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EnergyRecordCreate(BaseModel):
    meter_id: int
    consumption_kwh: float
    voltage: float | None = None
    current: float | None = None
    power: float | None = None
    power_factor: float | None = None
    timestamp: datetime | None = None


class EnergyRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meter_id: int
    timestamp: datetime
    consumption_kwh: float
    voltage: float | None
    current: float | None
    power: float | None


class EnergySummary(BaseModel):
    total_records: int
    total_consumption_kwh: float
    average_consumption_kwh: float
