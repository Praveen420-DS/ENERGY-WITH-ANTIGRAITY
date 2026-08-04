# Electricity Candidate Backend Integration

This endpoint is for controlled evaluation only. It does not replace or modify production v1.0.0.

## Configuration

The candidate is disabled by default:

```env
ELECTRICITY_CANDIDATE_ENABLED=false
ELECTRICITY_CANDIDATE_PACKAGE=models/candidates/v2.0.0-electricity
```

Set the enable flag to `true` only in an authorized test deployment. The path must remain a repository-relative `models/candidates/...` path. Checksums and exact runtime dependencies are validated before trusted joblib deserialization. A candidate failure leaves v1 loaded and operational.

## API

- `GET /api/electricity-candidate/health` is public and reports only disabled, unavailable, or ready state.
- `POST /api/electricity-candidate/predict` requires the existing JWT and accepts `input_timestamp`, optional fixed `meter: 0`, and the exact ordered technical `features` object from the package example.

The response uses `predicted_electricity_consumption_value`, candidate version/status, electricity-only scope, `output_unit: unverified`, timestamps, and warnings. It contains no confidence, cost, carbon, savings, or production claim. Results are not persisted to production history.

Unknown categories are safely ignored by the fitted encoder with a warning. Missing fields, unexpected fields, nonfinite numbers, non-electricity meter values, and incompatible ordering are rejected with safe structured errors and request IDs. A candidate-only backend token bucket matches the production prediction policy at 10 requests/second with burst 20, while unchanged Nginx also applies its existing `/api` limit. CORS, CSP, authentication, and request-ID middleware are unchanged.

## Enable, disable, and rollback

Restart the backend after changing the explicit enable flag. Disable it and restart to unload the candidate. Production v1.0.0 remains the rollback/current path throughout.

## Limitations and promotion blockers

Peak errors, later-period degradation, unit verification, training-cap sensitivity, XGBoost evaluation, and broader integration validation remain open. This endpoint is not production-approved.

## Tests

```bash
python -m pytest backend/tests/test_electricity_candidate_integration.py -q
python -m pytest backend/tests -q
```
