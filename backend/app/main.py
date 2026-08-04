"""FastAPI application factory and security middleware."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import Settings
from app.database import engine
from app.docs import JSON_CSP, SWAGGER_CSP, swagger_ui_html
from app.ml.model_manager import get_model_manager
from app.ml.electricity_candidate_manager import ElectricityCandidateError, get_electricity_candidate_manager
from app.routers import (
    alerts,
    anomalies,
    auth,
    energy,
    electricity_predictions,
    meters,
    models,
    predictions,
    system,
    users,
)

settings = Settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger(__name__)
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Load trusted model state and verify the migrated database at startup."""
    configured: Settings = application.state.settings
    LOGGER.info("Application startup started")
    if configured.app_env.lower() != "production" and len(
        configured.jwt_secret_key
    ) < 32:
        LOGGER.warning(
            "Development JWT secret is shorter than 32 characters; "
            "replace it before shared use."
        )
    manager = get_model_manager()
    production_model = manager.load(configured.production_model_manifest)
    application.state.production_model_manager = manager
    application.state.production_model = production_model
    candidate_manager = get_electricity_candidate_manager()
    if configured.electricity_candidate_enabled:
        try: candidate_manager.load(configured.electricity_candidate_package)
        except ElectricityCandidateError: LOGGER.error("Application continuing with production v1; electricity candidate unavailable")
    else: candidate_manager.clear()

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        LOGGER.info("Database connection verified after migrations")
        LOGGER.info(
            "Application startup completed model_version=%s checksum=verified",
            manager.version,
        )
        yield
    finally:
        LOGGER.info("Application shutdown started")
        manager.clear()
        candidate_manager.clear()
        await engine.dispose()
        LOGGER.info("Application shutdown completed")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    """Build the API with environment-specific documentation exposure."""
    configured = app_settings or settings
    application = FastAPI(
        title=configured.app_name,
        version=configured.app_version,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if configured.docs_enabled else None,
    )
    application.state.settings = configured

    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured.allowed_origins.split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """Attach safe request IDs, route CSP, and structured access logs."""
        incoming = request.headers.get("X-Request-ID", "")
        request_id = (
            incoming if SAFE_REQUEST_ID.fullmatch(incoming) else str(uuid4())
        )
        request.state.request_id = request_id
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            LOGGER.exception(
                "HTTP request failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
            raise
        elapsed_ms = (perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path == "/docs" or request.url.path.startswith(
            "/static/swagger-ui/"
        ):
            response.headers["Content-Security-Policy"] = SWAGGER_CSP
        elif request.url.path == "/openapi.json" or request.url.path.startswith(
            "/api/"
        ):
            response.headers["Content-Security-Policy"] = JSON_CSP
        LOGGER.info(
            "HTTP request completed request_id=%s method=%s path=%s "
            "status=%d latency_ms=%.3f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @application.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Return client-safe prediction validation details."""
        is_candidate = request.url.path.startswith("/api/electricity-candidate")
        if not request.url.path.startswith("/api/predictions") and not is_candidate:
            return await request_validation_exception_handler(request, exc)
        details = [
            {
                "field": ".".join(str(item) for item in error["loc"][1:])
                or None,
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_CANDIDATE_INPUT" if is_candidate else "INVALID_PREDICTION_INPUT",
                    "message": "The candidate request payload is invalid." if is_candidate else "The request payload is invalid.",
                    "details": details,
                    "request_id": getattr(
                        request.state,
                        "request_id",
                        str(uuid4()),
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

    @application.exception_handler(HTTPException)
    async def structured_http_error(request: Request, exc: HTTPException):
        """Preserve safe FastAPI errors and known structured envelopes."""
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return await http_exception_handler(request, exc)

    @application.exception_handler(Exception)
    async def safe_unhandled_error(request: Request, exc: Exception):
        """Log unexpected failures while returning a non-sensitive contract."""
        request_id = getattr(request.state, "request_id", str(uuid4()))
        LOGGER.exception(
            "Unhandled application error request_id=%s path=%s",
            request_id,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            headers={
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Content-Security-Policy": JSON_CSP,
            },
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "The request could not be completed.",
                    "request_id": request_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

    @application.get("/health", tags=["system"])
    async def liveness():
        """Report process liveness without implying model readiness."""
        return {"status": "alive"}

    if configured.docs_enabled:
        static_directory = Path(__file__).resolve().parent / "static"
        application.mount(
            "/static",
            StaticFiles(directory=static_directory),
            name="static",
        )

        @application.get("/docs", include_in_schema=False)
        async def api_docs():
            return swagger_ui_html(
                f"{configured.app_name} - Swagger UI"
            )

    application.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    application.include_router(users.router, prefix="/api/users", tags=["users"])
    application.include_router(meters.router, prefix="/api/meters", tags=["meters"])
    application.include_router(energy.router, prefix="/api/energy", tags=["energy"])
    application.include_router(
        predictions.router,
        prefix="/api/predictions",
        tags=["predictions"],
    )
    application.include_router(electricity_predictions.router,prefix="/api/electricity-candidate",tags=["experimental-electricity-candidate"])
    application.include_router(
        anomalies.router,
        prefix="/api/anomalies",
        tags=["anomalies"],
    )
    application.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
    application.include_router(models.router, prefix="/api/models", tags=["models"])
    application.include_router(system.router, prefix="/api/system", tags=["system"])
    return application


app = create_app()
