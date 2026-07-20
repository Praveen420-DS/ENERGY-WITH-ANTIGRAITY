from pydantic import BaseModel

class AlertConfig(BaseModel):
    meter_id: str
    threshold_kwh: float
    email_enabled: bool = True
    sms_enabled: bool = False

class AlertNotification(BaseModel):
    meter_id: str
    message: str
