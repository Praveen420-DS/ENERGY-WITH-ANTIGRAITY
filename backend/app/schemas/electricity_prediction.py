from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ElectricityCandidateRequest(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    input_timestamp: datetime
    meter: int|None=Field(default=None,ge=0,le=3)
    features: dict[str, Any]
    @field_validator("input_timestamp")
    @classmethod
    def naive_timestamp(cls,value):
        if value.tzinfo is not None: raise ValueError("input_timestamp must be timezone-naive")
        return value

class ElectricityCandidateResponse(BaseModel):
    predicted_electricity_consumption_value: float=Field(ge=0,allow_inf_nan=False)
    model_version:str; model_status:Literal["candidate"]="candidate"; dataset_scope:Literal["electricity_only"]="electricity_only"; output_unit:Literal["unverified"]="unverified"
    prediction_timestamp:datetime; input_timestamp:datetime; warnings:list[str]

class ElectricityCandidateHealth(BaseModel):
    status:Literal["disabled","unavailable","ready"]; enabled:bool; model_loaded:bool; model_version:str|None; checksum_status:Literal["verified","not_verified"]
