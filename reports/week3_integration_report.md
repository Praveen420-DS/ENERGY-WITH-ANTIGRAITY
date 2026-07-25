# Week 3 Production ML Integration Report

## Executive summary

Week 3 integrated the validated Random Forest package into the existing
FastAPI and React application without retraining or changing Week 2 inference.
The authenticated API accepts all 15 raw application fields, delegates to
`ml_service/inference.py`, returns a finite nonnegative prediction, preserves
inference warnings, and matches direct inference exactly for the committed
example.

The React dashboard now provides an accessible raw-input form, loading and error
states, sample/reset controls, and a structured result view. Frontend build and
lint pass. The result is **CONDITIONALLY READY FOR WEEK 4** because Docker
Desktop and PostgreSQL were unavailable for container runtime and the existing
database-backed test suite.

## Objective and scope

The objective was application integration only: model lifecycle, API contract,
frontend prediction workflow, Docker packaging, validation, and documentation.
No model training, feature-formula changes, dataset changes, model selection,
monitoring, cloud deployment, or Week 4 work was performed.

## Architecture audit

Before Week 3:

- FastAPI entry point: `backend/app/main.py`, served as `app.main:app`.
- API convention: routers registered under `/api`.
- Lifecycle: modern FastAPI lifespan context manager.
- CORS: previously unrestricted.
- Authentication: OAuth2 password flow and existing JWT bearer dependency.
- Predictions: authenticated history-only `GET /api/predictions/`.
- Health: database-aware `GET /api/system/health`.
- Tests: FastAPI `TestClient`; existing fixtures require PostgreSQL.
- Frontend: React 19/Vite dashboard with local section state and one Axios
  instance; no React router and no frontend test framework.
- Frontend API: hardcoded host URL, with JWT interceptor.
- Docker services: `nginx`, `frontend`, `backend`, `celery-worker`,
  `celery-beat`, `postgres`, and `redis`.
- Nginx: `/api/`, `/docs`, and `/openapi.json` proxied to `backend:8000`.

After Week 3:

```text
React PredictionPage
  -> existing Axios client + JWT
  -> POST /api/predictions/
  -> ProductionPredictionRequest
  -> PredictionService
  -> ProductionModelManager
  -> ml_service/inference.py
  -> models/production/current.json
  -> active checksum-verified package
  -> ProductionPredictionResponse
```

## Files created

- `backend/app/ml/model_manager.py`
- `backend/app/ml/loader.py`
- `backend/app/ml/predictor.py`
- `backend/app/ml/__init__.py`
- `backend/tests/ml_test_utils.py`
- `backend/tests/test_app_lifecycle.py`
- `backend/tests/test_model_manager.py`
- `backend/tests/test_prediction_api.py`
- `backend/tests/test_prediction_service.py`
- `backend/tests/test_prediction_validation.py`
- `frontend/src/components/PredictionForm.jsx`
- `frontend/src/components/PredictionResult.jsx`
- `frontend/src/pages/PredictionPage.jsx`
- `frontend/src/prediction.css`
- `reports/week3_integration_report.md`
- `reports/week3_integration_metrics.json`
- `reports/week3_integration.log`

## Files modified

- `.env.example`
- `.gitignore`
- `README.md`
- `backend/Dockerfile`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/routers/predictions.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/prediction.py`
- `backend/app/services/prediction_service.py`
- `docker/docker-compose.yml`
- `docker/docker-compose.dev.yml`
- `docker/nginx/nginx.conf`
- `docs/api_reference.md`
- `docs/deployment_guide.md`
- `frontend/src/main.jsx`
- `frontend/src/pages/Dashboard.jsx`
- `frontend/src/services/api.js`
- `frontend/vite.config.js`

## Model lifecycle

`ProductionModelManager` only accepts `current.json` inside the trusted
repository production directory. It delegates loading and checksum validation
to `ml_service.inference.load_production_model`, validates the minimum runtime
files, caches one runtime per process, and exposes defensive metadata,
readiness, version, checksum status, load timestamp, and load count.

FastAPI initializes the manager before database startup. Any model failure
aborts startup. Shutdown releases manager references without deleting or
modifying artifacts. The isolated lifecycle test confirms a single load and the
log message `Production model v1.0.0 loaded successfully`.

## API input contract

All production-schema fields are required: `building_id`, `meter`, `timestamp`,
`site_id`, `primary_use`, `square_feet`, `year_built`, `floor_count`,
`air_temperature`, `cloud_coverage`, `dew_temperature`,
`precip_depth_1_hr`, `sea_level_pressure`, `wind_direction`, and `wind_speed`.

Pydantic rejects extra properties, including `meter_reading`; NaN/infinity;
timezone-aware or malformed timestamps; invalid meter codes; negative area;
years outside 1800–2016; nonpositive floors; and wind direction outside
0–360. Inference repeats authoritative domain validation before Week 2 feature
engineering.

## API response and errors

The response includes the prediction, resolved model version, prediction and
input timestamps, meter, unit note, warnings, request ID, and processing time.
It contains no confidence field.

Prediction validation errors use a client-safe envelope with code, message,
field details, request ID, and timestamp. Model unavailability maps to HTTP 503;
domain input errors to HTTP 400; schema errors to HTTP 422; and unexpected
prediction failures to HTTP 500. Stack traces and internal paths are not
returned.

## Health and readiness

- `GET /health`: application liveness only.
- `GET /api/predictions/health`: model readiness and safe metadata.
- Existing `GET /api/system/health`: preserved.

Readiness returns HTTP 503 when the manager is not initialized.

## Authentication decision

The prediction endpoint requires the existing JWT dependency, matching all
established dashboard data routes. Readiness and liveness remain public for
probes. No second JWT implementation or test token was introduced.

## Logging

Logs cover model-load start/success/failure, resolved version, request start,
completion, processing time, warning count, and safe error categories. Tokens,
secrets, complete input payloads, and response stack traces are not logged.

## Backend and parity results

- Focused Week 3 tests: **24 passed, 0 failed**.
- Full backend collection: **24 Week 3 tests passed; 4 existing tests errored
  at setup** because PostgreSQL refused the connection.
- Week 2 tests: **30 passed, 0 failed**.
- Week 2 production smoke checks: **16/16 passed**.
- Direct prediction: `174.33691959802735`.
- FastAPI prediction: `174.33691959802735`.
- Absolute parity difference: `0.0`.
- Unknown category/identifier behavior: accepted with three inference warnings.
- Model artifact SHA-256:
  `67f244e576cb2b2b161a04f72499e5b00d2ac2361669561472edee5a14bff507`.

No training dataset is referenced by Week 3 runtime code or tests.

## Performance

Measured locally in a clean Python process:

- model initialization: 1628.95 ms;
- first API request: 66.38 ms;
- 100 warm requests minimum: 47.14 ms;
- mean: 52.72 ms;
- median: 50.77 ms;
- p95: 60.38 ms;
- maximum: 131.08 ms;
- sequential throughput: 18.97 requests/s;
- successful model load count: 1.

Warm median and p95 satisfy the preferred sub-100 ms target.

## Frontend integration

The form sends only the 15 raw inputs. It does not calculate engineered
features and never sends `meter_reading`. It provides valid meter choices,
native HTML constraints, field errors, sample/reset actions, loading and
duplicate-submit protection, and retains values after server errors.

The result presents meter type, raw prediction, model version, timestamps,
processing time, unit note, request ID, and warnings. It includes no confidence,
billing, savings, or control claims.

Frontend `npm run build` and `npm run lint` passed. No frontend test framework
exists, so a new large test stack was intentionally not introduced.

## Docker and Nginx

The backend build context is the project root so runtime code can include the
manifest and package. The image copies only the inference module, required Week
2 feature module, and production package—not training datasets or notebooks.
Development mounts model artifacts read-only.

Nginx proxies `/api/`, `/health`, `/docs`, and `/openapi.json`. The frontend
uses `/api` by default, and Vite proxies it during local development.

Compose configuration validation passed. Image build and runtime validation
could not run because the Docker Desktop Linux engine pipe was unavailable.

## Security and robustness review

- Only repository-controlled `models/production/current.json` may be selected.
- Active package traversal outside `models/production` is rejected.
- Joblib/pickle artifacts are trusted-code artifacts and must never come from
  users or untrusted remote sources.
- Model upload functionality was not added.
- Request fields are closed and finite; malformed JSON is handled by FastAPI.
- No batch endpoint was added, avoiding an unneeded memory/request-size surface.
- CORS now uses configured explicit origins rather than `*`.
- JWT authentication is reused.
- Client responses do not disclose secrets, paths, credentials, or tracebacks.

## Infrastructure issues

- Docker Desktop Linux daemon was not running, blocking image and container
  runtime validation.
- PostgreSQL was not listening locally, blocking four existing database-backed
  tests and a normal host startup.
- Live running-backend and browser parity could not be executed.
- Frontend component tests are unavailable because the project has no frontend
  test framework.

## Production-model limitations

- Meter units depend on meter type.
- Performance is weak for extreme target values.
- Temporal drift is substantial.
- Low explained variance remains a risk.
- Predictions are not approved for billing.
- Predictions are not approved for safety-critical control.
- Predictions do not guarantee financial savings.

See `models/production/v1.0.0/model_card.md` for the validated model card.

## Week 4 readiness

**CONDITIONALLY READY FOR WEEK 4 (92%)**. Critical model loading, checksum,
request validation, authenticated API, direct/API parity, frontend build, and
Compose configuration are green. Before Week 4, start Docker Desktop and run
the full Compose stack, database-backed regression tests, running HTTP parity,
and browser submission flow.
