"""Prediction API request, response, readiness, and error contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ProductionPredictionRequest(BaseModel):
    """Raw application-level input accepted by production inference."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        json_schema_extra={
            "examples": [
                {
                    "building_id": 0,
                    "meter": 0,
                    "actual_kwh": 174.3,
                    "timestamp": "2016-07-15T14:00:00",
                    "site_id": 0,
                    "primary_use": "Education",
                    "square_feet": 7432,
                    "year_built": 2008,
                    "floor_count": 4,
                    "air_temperature": 25.0,
                    "cloud_coverage": 6.0,
                    "dew_temperature": 20.0,
                    "precip_depth_1_hr": 0.0,
                    "sea_level_pressure": 1019.7,
                    "wind_direction": 180.0,
                    "wind_speed": 3.1,
                }
            ]
        },
    )

    building_id: int = Field(ge=0, description="Nonnegative building identifier.")
    actual_kwh: float | None = Field(
        default=None,
        ge=0,
        description="Optional observed electricity consumption in kWh; not an ML feature.",
    )
    meter: Literal[0, 1, 2, 3] = Field(
        description=(
            "Meter type: 0 electricity, 1 chilled water, "
            "2 steam, 3 hot water."
        )
    )
    timestamp: datetime = Field(
        description="Timezone-naive ISO-8601 observation timestamp."
    )
    site_id: int = Field(ge=0, description="Nonnegative site identifier.")
    primary_use: str = Field(
        min_length=1,
        description="Building primary-use category; unknown values are warned.",
    )
    square_feet: float = Field(
        ge=0,
        description="Building area in square feet.",
    )
    year_built: float = Field(
        ge=1800,
        le=2016,
        description="Building construction year.",
    )
    floor_count: float = Field(
        gt=0,
        description="Positive building floor count.",
    )
    air_temperature: float = Field(description="Finite air temperature.")
    cloud_coverage: float = Field(description="Finite cloud coverage.")
    dew_temperature: float = Field(description="Finite dew temperature.")
    precip_depth_1_hr: float = Field(
        description=(
            "Finite hourly precipitation depth; negative training sentinels "
            "remain valid."
        )
    )
    sea_level_pressure: float = Field(description="Finite sea-level pressure.")
    wind_direction: float = Field(
        ge=0,
        le=360,
        description="Wind direction in degrees.",
    )
    wind_speed: float = Field(description="Finite wind speed.")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Enforce the production timestamp range and timezone contract."""
        if value.tzinfo is not None:
            raise ValueError("timestamp must be timezone-naive")
        if not 1900 <= value.year <= 2100:
            raise ValueError("timestamp year must be between 1900 and 2100")
        return value

    @field_validator("primary_use")
    @classmethod
    def strip_primary_use(cls, value: str) -> str:
        """Reject whitespace-only categories and normalize surrounding space."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("primary_use must be a non-empty string")
        return normalized

    def to_inference_record(self) -> dict[str, Any]:
        """Return the exact raw record contract expected by inference."""
        record = self.model_dump(exclude={"actual_kwh"})
        record["timestamp"] = self.timestamp.isoformat()
        return record


class ProductionPredictionResponse(BaseModel):
    """Structured response from one production prediction."""

    predicted_meter_reading: float = Field(ge=0, allow_inf_nan=False)
    model_version: str
    prediction_timestamp: datetime
    input_timestamp: datetime
    meter: Literal[0, 1, 2, 3]
    unit_note: str
    warnings: list[str]
    request_id: str
    processing_time_ms: float = Field(ge=0, allow_inf_nan=False)


class ModelReadinessResponse(BaseModel):
    """Public-safe production readiness response."""

    status: Literal["ready", "not_ready"]
    model_loaded: bool
    model_version: str | None
    algorithm: str | None
    schema_version: str | None
    loaded_at: datetime | None
    checksum_status: Literal["verified", "not_verified"]


class ErrorDetail(BaseModel):
    """One structured API error detail."""

    field: str | None = None
    message: str


class ErrorBody(BaseModel):
    """Client-safe API error body."""

    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Consistent API error envelope."""

    error: ErrorBody


class PredictionRead(BaseModel):
    """Existing persisted prediction history response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    meter_id: int
    horizon: str
    predicted_at: datetime
    target_start: datetime
    predicted_kwh: float
    actual_kwh: float | None = None
    confidence: float
