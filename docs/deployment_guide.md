# Deployment and Local Run Guide

## Prerequisites

- Windows 10/11 with Docker Desktop using the WSL 2 Linux-container engine
- Docker Engine 29+ and Docker Compose v2+
- At least 4 GB free Docker memory and 3 GB free disk space
- Node.js 20+ and Python 3.12 only for host-side development

Confirm Docker before continuing:

```powershell
docker version
docker context show
docker info --format '{{.OSType}}'
docker compose version
```

`docker info` must report `linux`. Start Docker Desktop manually if its daemon
is unavailable.

## Environment and secrets

```powershell
Copy-Item .env.example .env
```

Replace every placeholder password and JWT value in `.env`. A suitable local
JWT secret can be generated without displaying it in shell history:

```powershell
$bytes = New-Object byte[] 48
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

Keep `PRODUCTION_MODEL_MANIFEST=models/production/current.json`,
`VITE_API_URL=/api`, and restrict `ALLOWED_ORIGINS` to trusted origins. The
application refuses known placeholder JWT secrets when `APP_ENV=production`.
Never commit `.env`.

## Production-like local startup

Run from the repository root:

```powershell
docker compose -f docker/docker-compose.yml config
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps -a
```

Compose starts PostgreSQL and Redis, applies `alembic upgrade head` in a
one-shot migration service, loads the production model in the backend, starts
Celery worker/beat, initializes the frontend volume, and finally starts Nginx.
The frontend initializer exiting with code 0 is expected.

Development overrides:

```powershell
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
```

Validate production overrides without publishing internal service ports:

```powershell
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml config
```

## URLs and complete user flow

- Frontend: <http://localhost/>
- Backend direct: <http://localhost:8000/>
- Swagger through Nginx: <http://localhost/docs>
- Liveness: <http://localhost/health>
- Model readiness: <http://localhost/api/predictions/health>

Register or sign in through the frontend, open **Prediction**, choose **Use
sample**, and submit. The browser sends only raw observations. Feature
engineering and inference execute server-side through `ml_service/inference.py`.
The production sample result is approximately `174.33691959802735`; the UI
displays `174.3369`.

## Migrations and health checks

```powershell
docker compose -f docker/docker-compose.yml run --rm migrate
docker compose -f docker/docker-compose.yml exec postgres pg_isready -U postgres
docker compose -f docker/docker-compose.yml exec redis redis-cli ping
Invoke-RestMethod http://localhost/health
Invoke-RestMethod http://localhost/api/predictions/health
```

Migration execution is idempotent. Do not use ORM `create_all` as a deployment
substitute.

## Logs, restart, and shutdown

```powershell
docker compose -f docker/docker-compose.yml logs --tail 100 backend nginx postgres redis celery-worker celery-beat
docker compose -f docker/docker-compose.yml restart backend
docker compose -f docker/docker-compose.yml down
```

`down` preserves named volumes. Never add `--volumes` unless irreversible data
removal is explicitly intended and a backup is verified.

## Backup and restore

```powershell
docker compose -f docker/docker-compose.yml exec -T postgres pg_dump -U postgres -d energy_prediction -Fc > energy_prediction.dump
Get-Content energy_prediction.dump -AsByteStream -Raw | docker compose -f docker/docker-compose.yml exec -T postgres pg_restore -U postgres -d energy_prediction --clean --if-exists
```

Test restores on a non-production database first. Protect dumps as sensitive
data and stop application writes during a consistency-sensitive restore.

## Troubleshooting and recovery

- Docker daemon errors: start Docker Desktop, select Linux containers, then
  rerun `docker version` and `docker context show`.
- PostgreSQL unhealthy: inspect `docker compose ... logs postgres`, confirm
  `.env` matches the initialized volume, and restore from backup if corruption
  is confirmed. Do not delete the volume as a diagnostic shortcut.
- Password authentication after changing `.env`: PostgreSQL initialization
  credentials do not rewrite an existing volume. Restore/migrate credentials
  deliberately rather than inspecting or deleting data.
- Migration failure: inspect migration logs and `alembic current`; fix forward
  and rerun the one-shot service.
- Model checksum failure: restore the trusted `v1.0.0` package from source
  control. Do not regenerate checksums around an unexplained change.
- Model readiness 503: inspect backend startup logs; readiness intentionally
  omits internal paths and stack traces.
- Frontend network error: confirm backend and Nginx health and that
  `VITE_API_URL=/api`.
- HTTP 401: sign in again. HTTP 422 means the raw request contract failed.
- HTTP 503 under bursts: Nginx limits `/api/` to 10 requests/second with a
  burst of 20; retry with backoff.

## Security and model limitations

The backend and Python workers run as a non-root user, and production model
files are read-only in the image. Nginx applies request-size/rate limits and
browser security headers. Joblib artifacts are pickle-based: load only the
trusted repository-controlled package.

Predictions are informational, meter units depend on the meter code, and
unknown categories or out-of-training-period timestamps can increase error.
The result is not a billing value, confidence score, safety control, or
guarantee. Negative model outputs are clipped to zero.
