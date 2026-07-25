# API Reference

The FastAPI service exposes interactive OpenAPI documentation at `/docs`.

## Authentication

`POST /api/predictions/` follows the existing application policy and requires
a JWT bearer token returned by `POST /api/auth/login`. The liveness and model
readiness endpoints are public.

## Application liveness

`GET /health`

```json
{"status": "alive"}
```

Liveness only confirms that the application process can answer requests.

## Production-model readiness

`GET /api/predictions/health`

A ready response includes safe model metadata:

```json
{
  "status": "ready",
  "model_loaded": true,
  "model_version": "v1.0.0",
  "algorithm": "RandomForestRegressor",
  "schema_version": "1.0.0",
  "loaded_at": "2026-07-25T15:00:00Z",
  "checksum_status": "verified"
}
```

The endpoint returns HTTP 503 with `status: "not_ready"` if the model is not
initialized. Local paths and model objects are never returned.

## Create a prediction

`POST /api/predictions/`

Headers:

```text
Authorization: Bearer <access-token>
Content-Type: application/json
```

Request:

```json
{
  "building_id": 0,
  "meter": 0,
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
  "wind_speed": 3.1
}
```

All fields are required. `meter_reading` and unknown additional properties are
rejected. The timestamp must be timezone-naive. Numeric values must be finite.
The valid meter codes are 0 electricity, 1 chilled water, 2 steam, and 3 hot
water.

Response:

```json
{
  "predicted_meter_reading": 174.33691959802735,
  "model_version": "v1.0.0",
  "prediction_timestamp": "2026-07-25T15:00:00Z",
  "input_timestamp": "2016-07-15T14:00:00",
  "meter": 0,
  "unit_note": "Units depend on meter type: electricity, chilled water, steam, and hot water use different meter-reading units.",
  "warnings": [],
  "request_id": "c3f29346-8245-4de8-97db-cf77138ddbc4",
  "processing_time_ms": 51.2
}
```

Unknown `primary_use`, building IDs, and site IDs remain accepted when the
production inference contract allows them and produce explicit warnings.

## Error contract

Schema errors return HTTP 422, domain validation errors return HTTP 400, model
unavailability returns HTTP 503, and unexpected prediction-processing errors
return HTTP 500. Client-safe prediction errors use:

```json
{
  "error": {
    "code": "INVALID_PREDICTION_INPUT",
    "message": "The request payload is invalid.",
    "details": [
      {"field": "meter", "message": "Input should be 0, 1, 2 or 3"}
    ],
    "request_id": "c3f29346-8245-4de8-97db-cf77138ddbc4",
    "timestamp": "2026-07-25T15:00:00Z"
  }
}
```

Responses do not expose stack traces, credentials, artifact paths, or model
internals.

## Limitations

Meter-reading units depend on the meter type. Predictions are informational:
they are not approved for billing, safety-critical control, or guaranteed
financial savings. See the
[production model card](../models/production/v1.0.0/model_card.md) for the full
validated limitations.
