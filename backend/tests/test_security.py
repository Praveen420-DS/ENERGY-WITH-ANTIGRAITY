"""Focused documentation, authentication, CORS, and artifact security tests."""

from datetime import datetime, timedelta, timezone
import shutil
import stat

from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError
import pytest

from app.config import Settings, validate_test_database_separation
from app.docs import SWAGGER_CSP
from app.main import create_app
from app.ml import model_manager as manager_module
from app.ml.model_manager import (
    ProductionModelManager,
    ProductionModelManagerError,
)
from app.schemas.user import UserCreate
from app.utils.exceptions import AuthenticationError
from app.utils.security import decode_access_token, settings as jwt_settings
from ml_test_utils import MANIFEST


def settings_for(environment: str, docs: bool | None = None) -> Settings:
    values = {
        "_env_file": None,
        "APP_ENV": environment,
        "JWT_SECRET_KEY": "s" * 40,
        "DATABASE_URL": (
            "postgresql+asyncpg://app:strong-password@postgres/"
            "energy_prediction"
        ),
        "ALLOWED_ORIGINS": "http://localhost,http://localhost:5173",
    }
    if docs is not None:
        values["API_DOCS_ENABLED"] = docs
    return Settings(**values)


def test_docs_enabled_in_development_and_assets_are_local():
    application = create_app(settings_for("development"))
    client = TestClient(application, raise_server_exceptions=False)

    response = client.get("/docs")
    assert response.status_code == 200
    assert "https://" not in response.text
    assert "http://" not in response.text
    assert "/static/swagger-ui/swagger-ui.css" in response.text
    assert "/static/swagger-ui/swagger-ui-bundle.js" in response.text
    assert "/static/swagger-ui/swagger-initializer.js" in response.text
    assert "<script>" not in response.text
    assert client.get("/static/swagger-ui/swagger-ui.css").headers[
        "content-type"
    ].startswith("text/css")
    assert "javascript" in client.get(
        "/static/swagger-ui/swagger-ui-bundle.js"
    ).headers["content-type"]


def test_docs_csp_is_strict_and_not_duplicated():
    client = TestClient(
        create_app(settings_for("development")),
        raise_server_exceptions=False,
    )
    response = client.get("/docs")
    policies = response.headers.get_list("content-security-policy")
    assert policies == [SWAGGER_CSP]
    assert "*" not in SWAGGER_CSP
    assert "'unsafe-eval'" not in SWAGGER_CSP
    assert "'unsafe-inline'" not in SWAGGER_CSP


def test_docs_openapi_and_static_are_disabled_by_default_in_production(
    monkeypatch,
):
    monkeypatch.delenv("API_DOCS_ENABLED", raising=False)
    client = TestClient(
        create_app(settings_for("production")),
        raise_server_exceptions=False,
    )
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/static/swagger-ui/swagger-ui.css").status_code == 404


def test_openapi_declares_prediction_oauth2_security():
    schema = create_app(settings_for("development")).openapi()
    operation = schema["paths"]["/api/predictions/"]["post"]
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    scheme = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    assert scheme["flows"]["password"]["tokenUrl"] == "/api/auth/login"


def test_cors_accepts_only_configured_origin_and_authorization_header():
    client = TestClient(
        create_app(settings_for("development")),
        raise_server_exceptions=False,
    )
    allowed = client.options(
        "/health",
        headers={
            "Origin": "http://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost"
    assert "Authorization" in allowed.headers["access-control-allow-headers"]

    rejected = client.options(
        "/health",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.parametrize(
    "origin",
    ["*", "javascript://example.com", "https://example.com/path"],
)
def test_malformed_cors_origins_are_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ALLOWED_ORIGINS=origin)


def test_placeholder_short_secret_and_default_database_password_are_rejected():
    base = {
        "_env_file": None,
        "APP_ENV": "production",
        "DATABASE_URL": (
            "postgresql+asyncpg://app:strong-password@postgres/"
            "energy_prediction"
        ),
    }
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(**base, JWT_SECRET_KEY="CHANGE_ME")
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(**base, JWT_SECRET_KEY="short")
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET_KEY="s" * 40,
            DATABASE_URL=(
                "postgresql+asyncpg://postgres:postgres@postgres/"
                "energy_prediction"
            ),
        )


def test_test_database_cannot_equal_production_database():
    url = "postgresql+asyncpg://app:strong-password@postgres/energy_prediction"
    with pytest.raises(ValueError, match="TEST_DATABASE_URL"):
        validate_test_database_separation(url, url)


def test_registration_normalizes_email_and_rejects_oversize_unicode_password():
    user = UserCreate(email="  E2ETest@Example.COM ", password="securepass123")
    assert str(user.email) == "e2etest@example.com"
    with pytest.raises(ValidationError, match="72 UTF-8 bytes"):
        UserCreate(email="person@example.com", password="é" * 40)


def test_invalid_and_expired_jwt_are_rejected_without_token_details():
    with pytest.raises(AuthenticationError, match="Token validation failed"):
        decode_access_token("not-a-token")
    expired = jwt.encode(
        {
            "sub": "person@example.com",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        jwt_settings.jwt_secret_key,
        algorithm=jwt_settings.jwt_algorithm,
    )
    with pytest.raises(AuthenticationError, match="Token validation failed"):
        decode_access_token(expired)


def test_manifest_path_traversal_is_rejected():
    with pytest.raises(ProductionModelManagerError, match="models/production"):
        ProductionModelManager().resolve_manifest("../../outside/current.json")


@pytest.mark.parametrize("failure", ["missing", "checksum"])
def test_temporary_package_failure_is_safe(tmp_path, monkeypatch, failure):
    copied_root = tmp_path / "production"
    shutil.copytree(MANIFEST.parent, copied_root)
    copied_manifest = copied_root / "current.json"
    model_path = copied_root / "v1.0.0" / "model.joblib"
    model_path.parent.chmod(model_path.parent.stat().st_mode | stat.S_IWUSR)
    model_path.chmod(model_path.stat().st_mode | stat.S_IWUSR)
    if failure == "missing":
        model_path.unlink()
    else:
        with model_path.open("ab") as model_file:
            model_file.write(b"security-test-corruption")

    monkeypatch.setattr(manager_module, "PRODUCTION_ROOT", copied_root.resolve())
    with pytest.raises(
        ProductionModelManagerError,
        match="Production model package could not be loaded",
    ):
        ProductionModelManager().load(copied_manifest)


def test_model_artifact_is_not_exposed_by_static_mount():
    client = TestClient(
        create_app(settings_for("development")),
        raise_server_exceptions=False,
    )
    response = client.get(
        "/static/swagger-ui/../../../models/production/v1.0.0/model.joblib"
    )
    assert response.status_code == 404
    assert "models/production" not in response.text


def test_unexpected_error_has_request_id_without_internal_details():
    application = create_app(settings_for("development"))

    @application.get("/security-test/error")
    async def intentional_error():
        raise RuntimeError("sensitive /absolute/path database-url-value")

    client = TestClient(application, raise_server_exceptions=False)
    response = client.get(
        "/security-test/error",
        headers={"X-Request-ID": "safe-test-request"},
    )
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["request_id"] == "safe-test-request"
    assert response.headers["X-Request-ID"] == "safe-test-request"
    assert "traceback" not in response.text.lower()
    assert "absolute/path" not in response.text
    assert "database-url-value" not in response.text
