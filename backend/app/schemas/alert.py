from pydantic import BaseModel, ConfigDict


class AlertConfigCreate(BaseModel):
    meter_id: int
    threshold_kwh: float
    email_enabled: bool = True
    sms_enabled: bool = False


class AlertConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    meter_id: int
    threshold_kwh: float
    email_enabled: bool
    sms_enabled: bool
    is_enabled: bool
