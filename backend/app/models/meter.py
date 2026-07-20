from pydantic import BaseModel
from typing import Optional

class Meter(BaseModel):
    id: Optional[str]
    name: str
    location: str
    capacity_kw: float
