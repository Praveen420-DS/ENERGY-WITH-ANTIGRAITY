from pydantic import BaseModel, ConfigDict, Field


class MeterCreate(BaseModel):
    meter_id: str
    name: str
    location: str
    capacity_kw: float = Field(ge=0)
    meter_type: str = "commercial"


class MeterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meter_id: str
    name: str
    location: str
    capacity_kw: float
    meter_type: str
    owner_id: int | None
    is_active: bool
