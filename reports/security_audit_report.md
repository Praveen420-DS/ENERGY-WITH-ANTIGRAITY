# Security Audit Report

Date: 2026-07-25  
Branch: `main`  
Baseline commit: `a57edd2`  
Environment: development Compose stack with production configuration inspected

## Executive summary

The application security correction is deployment-ready for a controlled
development environment. Swagger UI is self-hosted, its CSP is route-specific,
production documentation is disabled by default, JWT protection remains active,
production Compose publishes only Nginx port 80, and model artifacts are not
web-accessible. No Critical or High findings were identified.

Twelve findings were tracked: five Medium, five Low, and two Informational.
Nine are resolved. Three remain: the application/migration database credential
uses the PostgreSQL superuser (Medium), Redis has no authentication even though
it is internal-only in production (Low), and browser DevTools inspection could
not be performed because no browser was attached to the execution environment
(Informational).

## Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| M-01 | Medium | Default Swagger HTML used external assets blocked by CSP | Resolved |
| M-02 | Medium | API documentation was not environment-disabled in production | Resolved |
| M-03 | Medium | Authentication lacked a dedicated brute-force rate limit | Resolved |
| M-04 | Medium | An unused wildcard CORS helper could permit insecure future reuse | Resolved |
| M-05 | Medium | Application and migrations use the PostgreSQL superuser | Remaining |
| L-01 | Low | Frontend could retain a rejected token and logged auth responses | Resolved |
| L-02 | Low | Python containers lacked explicit read-only/capability controls | Resolved |
| L-03 | Low | Celery serialization allow-list was implicit | Resolved |
| L-04 | Low | Production override retained internal service host ports | Resolved |
| L-05 | Low | Redis default user has no password | Remaining |
| I-01 | Informational | Reported login user was absent from the current database | Resolved |
| I-02 | Informational | Browser console/network inspection unavailable in this session | Remaining |

## CSP and Swagger repair

The blank Swagger page was caused by FastAPI's CDN-hosted CSS, JavaScript and
favicon plus inline initialization being rejected by the strict Nginx CSP.
Pinned Swagger UI 5.30.3 assets are now stored under
`backend/app/static/swagger-ui/`. Initialization is in a local external file,
so neither a nonce nor `unsafe-inline` is required.

Nginx assigns exactly one CSP by route. It removes an upstream CSP before adding
the selected policy. React permits only same-origin application resources;
Swagger permits only same-origin scripts, styles, images and API connections;
JSON/API responses use `default-src 'none'`. Live raw-header checks found one
CSP, one `nosniff`, and one frame-protection header per response. No wildcard,
`unsafe-eval`, external CDN, or global `unsafe-inline` rule is present.

Development exposes `/docs`, `/openapi.json`, and local Swagger static files.
FastAPI itself omits those routes in production by default; this is not merely
an Nginx concealment. ReDoc remains disabled.

## Authentication, password, and JWT audit

The original `e2etest@example.com` 401 was valid: that account was not present
in the active PostgreSQL volume. Registration and login use the same database
and hashing implementation. A newly registered, uniquely named account logged
in successfully and predicted successfully.

Email is trimmed and lower-cased consistently. Passwords are hashed with the
project's established bcrypt/passlib implementation, are never stored or logged
as plaintext, and are bounded to 72 UTF-8 bytes to avoid bcrypt ambiguity.
Authentication logs contain only safe reason codes; clients always receive the
same generic 401 for unknown users, incorrect passwords, inactive users, and
malformed passwords.

JWT uses an explicitly configured HS256 allow-list and validates signature,
subject and expiration. Tokens include `iat` and `exp`. Production rejects
placeholder/short secrets and invalid algorithms. Tokens are accepted from the
Authorization header, never URLs. The frontend retains the existing
`localStorage` architecture, removes the token on logout and any 401, never
renders or logs it, and only sends it through the same-origin `/api` client.
The residual XSS implication of `localStorage` is mitigated by the strict CSP;
an HttpOnly-cookie migration was intentionally not attempted without a complete
CSRF design.

## CORS and request validation

Origins are explicit validated HTTP(S) origins. Credentials, wildcards, paths,
fragments, and malformed origins are rejected. Methods and headers are limited
to the application contract. Live preflight returned 200 for
`http://localhost:5173` and 400 for `https://evil.example`.

Prediction schemas forbid extra fields and reject NaN, infinities, wrong types,
invalid ranges, impossible timestamps, unsupported meters, and `meter_reading`.
Nginx rejects bodies above 64 KiB with structured 413 JSON.

## Nginx, headers, rate limits, and network exposure

Responses include CSP, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy`, and `Permissions-Policy`.
HSTS is intentionally absent on HTTP localhost. Nginx version tokens are hidden,
timeouts and body size are bounded, client forwarding headers are replaced from
the trusted connection, and request IDs are generated at the proxy.

Authentication is limited to 5 requests/minute with burst 5, predictions to
10/second with burst 20, and other APIs to 30/second. Health is not limited.
Live tests produced structured 429 responses for authentication and prediction
while health remained 200.

Development exposes 80, 8000, 5432 and 6379 for debugging. Production Compose
publishes only Nginx port 80; backend, PostgreSQL, Redis and Celery remain on the
internal network. TLS/HSTS must be configured at the real production edge.

## Model artifact security

Only the repository-controlled manifest under `models/production` selects the
model. The loader restricts versions, rejects traversal, verifies required files
and checksums before deserialization, and caches a single validated load. There
is no upload or remote-model endpoint. Python containers are read-only, their
embedded model package has no write bits, and Nginx explicitly returns 404 for
model, data, backend, ML-service, scripts, and dotfile paths.

Temporary-copy tests passed for traversal, missing artifacts, and checksum
corruption. Client errors do not disclose filesystem paths. The protected model
was not modified or retrained. The user-supplied formal validation reports
30/30 production tests and SHA-256
`67f244e576cb2b2b161a04f72499e5b00d2ac2361669561472edee5a14bff507`.

## Database, Redis, and Celery

SQLAlchemy ORM/parameterized queries are used; the only raw SQL found is the
constant health query `SELECT 1`. Test configuration refuses a database equal
to the application database. Duplicate registration is handled without
revealing internal SQL details.

The application and migrations still use the PostgreSQL superuser. Moving to
separate least-privilege runtime and migration roles requires a reviewed
ownership migration and was not performed against the existing volume.

Redis is internal in production but its default user is `nopass`. Add an
independently generated credential before an untrusted network can reach the
Docker network. Celery permits only JSON task/result serialization, workers are
non-root/read-only with all capabilities dropped, and Beat writes only its
schedule under `/tmp`.

## Frontend, secrets, dependencies, and containers

No `dangerouslySetInnerHTML`, external runtime script/style, open redirect,
source map, token log, or secret in the production bundle was found. API errors
are rendered as React text. Bundle scans found zero secret-name and zero actual
configured-secret hits.

`.env` is ignored and untracked. Production configuration rejects placeholder
JWT secrets and default database passwords. No private key appeared in the
practical Git-history scan. Secret values, passwords, JWTs, and database URLs
were redacted from validation output.

Container `pip check` reports no broken requirements. The successful dependency
scan found zero npm vulnerabilities; a later repeat could not reach the npm
audit endpoint and did not invalidate that result. No broad dependency upgrade
was performed. Backend, migration, worker and Beat run non-root, read-only,
without added capabilities or Docker socket mounts. Build contexts use
`.dockerignore`; the frontend runtime volume receives only built static assets.

## Tests and E2E results

- Backend application regression: 45 passed.
- Formal production model suite supplied by the user: 30 passed.
- Production smoke suite supplied by the user: 16 passed.
- Frontend: 14 passed; lint and production build passed.
- Security-focused backend checks cover docs modes/assets/CSP, JWT, CORS,
  secrets, database separation, model failures, static exposure, safe errors,
  request IDs, generic login, validation and authorization (17 focused tests).
- Compose development and production configurations validate.
- Images build and the full runtime is healthy: PostgreSQL, Redis, backend and
  Nginx healthy; Celery worker/Beat running; migration and frontend initializer
  exit successfully.
- Fresh registration: 201; normalized email confirmed.
- Login: 200; token returned but not recorded.
- Authenticated prediction: 200, model `v1.0.0`,
  `174.33691959802732`, absolute difference
  `2.842170943040401e-14` from the reference.
- Unauthenticated prediction and invalid-password login: generic 401.
- Swagger HTML and all four local assets: 200 with correct local references and
  MIME types; external Swagger request count: zero.
- Browser DevTools CSP/network confirmation is blocked because no browser is
  attached. Live HTTP, HTML inspection, automated tests and header checks pass,
  but they are not represented as a browser-console pass.

The database-backed subset was executed with a temporary role limited to the
test database. The role and its owned test objects were removed immediately
after the successful run.

## Error handling

400, 401, 404, 409, 413, 422 and 429 were exercised through tests or live HTTP.
Safe 500 and unavailable-service 503 behavior are automated. Reverse-proxy 502
recovery was validated by temporarily stopping and restarting only the backend;
no volume operation occurred. Responses contain no traceback, SQL statement,
database URL, JWT, password, backend service name, or absolute model path.
403 is not part of the current authorization contract.

## Remaining recommendations

1. Introduce a least-privilege PostgreSQL application role and a distinct
   migration owner using a reviewed, backed-up migration plan.
2. Configure Redis ACL authentication and update both Celery URLs before any
   network beyond the trusted Compose network can connect.
3. Run the documented browser-console/network checklist from a workstation with
   a browser and archive screenshots or HAR output.
4. Terminate TLS at the production edge, then enable HSTS there.
5. Rotate JWT, database and Redis credentials through the deployment secret
   store; never commit generated values.
