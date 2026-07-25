# Week 4 Deployment Readiness Report

## Decision

**CONDITIONALLY READY FOR DEPLOYMENT — 96% complete**

The production-like local stack builds and runs on Docker Desktop's Linux
engine. PostgreSQL and Redis are healthy, Alembic reaches head `001`, backend
readiness passes, Celery worker/beat run, Nginx serves the frontend, and direct,
container, and authenticated HTTP predictions return
`174.33691959802735`.

Full readiness is withheld because this execution environment exposed no
controllable browser for visual end-to-end validation. The unchanged Week 2
suite also has one inherited exact-bit determinism assertion that intermittently
differs by only `2.842170943040401e-14`; 29/30 pass and all artifact/contract
tests pass. No inference or Week 2 logic was changed to conceal this.

## Runtime evidence

| Area | Result |
|---|---|
| Docker | Desktop 4.82.0, Engine/CLI 29.6.1, Linux `desktop-linux` |
| Compose | Base, development, and production configurations valid |
| Images | Backend/migrate/Celery and frontend built successfully |
| Database | PostgreSQL healthy; test database usable; migrations idempotent |
| Services | Redis healthy; worker/beat running; backend/Nginx healthy |
| Model | v1.0.0, checksum verified, loaded once, artifact read-only |
| Backend tests | 28/28 passed in pinned image |
| Database tests | 4/4 passed |
| Frontend | 8/8 tests, lint, build, and npm audit passed |
| Performance | p50 53.10 ms; p95 55.55 ms; p99 71.44 ms |
| Recovery | Backend-down 502; static UI 200; readiness restored after start |

The frontend initializer is intentionally one-shot and exits 0 after copying
the immutable Vite build into the shared Nginx volume.

## Security and observability

- Backend and Python workers run as a non-root app user.
- Production model/provenance files are read-only in the image.
- Startup fails on model/checksum/database errors.
- Request IDs, status, method, path, and latency are logged without payloads,
  passwords, or tokens.
- Nginx applies a 64 KiB body limit, 10 requests/second rate limit, and browser
  security headers.
- Production mode rejects known placeholder JWT secrets.
- `pip check` and `npm audit` pass; npm reports zero known vulnerabilities.
- No CI workflow was added because it was optional and no remote integration
  was authorized.

## Integrity and scope

No model was retrained. No datasets, model package, production metadata,
checksums, Week 2 feature engineering, or `ml_service/inference.py` were
modified. `current.json` still selects `v1.0.0`; model SHA-256 remains
`67f244e576cb2b2b161a04f72499e5b00d2ac2361669561472edee5a14bff507`.
Feature engineering remains exclusively server-side. Predictions are finite,
nonnegative, and contain warnings rather than fabricated confidence scores.

No destructive database-volume operation, cloud deployment, commit/push, or
Week 5 work was performed.

## Remaining actions

1. Run the documented login/sample/invalid/network-recovery flow in a real
   browser when a browser surface is available.
2. Replace all local `.env` placeholders before any shared deployment.
3. In a separately authorized maintenance task, update the inherited
   determinism assertion to a documented floating-point tolerance after review;
   do not alter inference output to satisfy exact-bit equality.
