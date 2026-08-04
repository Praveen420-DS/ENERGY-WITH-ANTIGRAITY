"""Validated application configuration."""

from urllib.parse import urlsplit
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def validate_test_database_separation(
    production_url: str,
    test_url: str,
) -> None:
    """Reject test configuration that targets the production database."""
    production = make_url(production_url)
    test = make_url(test_url)
    if (
        production.host == test.host
        and production.port == test.port
        and production.database == test.database
    ):
        raise ValueError(
            "TEST_DATABASE_URL must not target the production database."
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        validate_default=True,
    )

    app_name: str = "Energy Prediction System"
    app_version: str = "0.1.0"
    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )
    api_docs_enabled: bool | None = Field(
        default=None,
        validation_alias="API_DOCS_ENABLED",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    production_model_manifest: str = Field(
        default="models/production/current.json",
        validation_alias="PRODUCTION_MODEL_MANIFEST",
    )
    electricity_candidate_enabled: bool = Field(default=False, validation_alias="ELECTRICITY_CANDIDATE_ENABLED")
    electricity_candidate_package: str = Field(default="models/candidates/v2.0.0-electricity", validation_alias="ELECTRICITY_CANDIDATE_PACKAGE")
    allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost",
        validation_alias="ALLOWED_ORIGINS",
    )

    database_url: str = Field(
        default=(
            "postgresql+asyncpg://postgres:postgres@"
            "postgres:5432/energy_prediction"
        ),
        validation_alias="DATABASE_URL",
    )
    migration_database_url: str | None = Field(
        default=None,
        validation_alias="MIGRATION_DATABASE_URL",
    )
    test_database_url: str | None = Field(
        default=None,
        validation_alias="TEST_DATABASE_URL",
    )
    redis_url: str = Field(
        default="redis://redis:6379/0",
        validation_alias="REDIS_URL",
    )
    celery_broker_url: str = Field(
        default="redis://redis:6379/0",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://redis:6379/1",
        validation_alias="CELERY_RESULT_BACKEND",
    )

    jwt_secret_key: str = Field(
        default="CHANGE_ME",
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_expiration_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        validation_alias="JWT_EXPIRATION_MINUTES",
    )

    @property
    def docs_enabled(self) -> bool:
        """Enable docs explicitly, otherwise default them off in production."""
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.app_env.lower() != "production"

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, value: str) -> str:
        """Accept only explicit HTTP(S) origins without paths or wildcards."""
        normalized: list[str] = []
        for candidate in value.split(","):
            origin = candidate.strip().rstrip("/")
            if not origin:
                continue
            parsed = urlsplit(origin)
            if (
                "*" in origin
                or parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"Invalid CORS origin: {origin!r}")
            normalized.append(origin)
        if not normalized:
            raise ValueError("ALLOWED_ORIGINS must contain at least one origin.")
        return ",".join(dict.fromkeys(normalized))

    @field_validator("electricity_candidate_package")
    @classmethod
    def validate_candidate_package(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("models", "candidates"):
            raise ValueError("ELECTRICITY_CANDIDATE_PACKAGE must be a trusted relative models/candidates path.")
        return path.as_posix()

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Reject unsupported JWT algorithms and unsafe production defaults."""
        unsafe_secrets = {
            "CHANGE_ME",
            "your-jwt-secret-change-in-production",
            "your-secret-key-change-in-production",
        }
        if self.jwt_algorithm != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256.")
        if self.app_env.lower() != "production":
            return self
        if self.jwt_secret_key in unsafe_secrets or len(self.jwt_secret_key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be a non-placeholder value of at least "
                "32 characters in production."
            )
        try:
            database_password = make_url(self.database_url).password
        except Exception as exc:
            raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL.") from exc
        if database_password in {None, "", "postgres", "changeme"}:
            raise ValueError(
                "DATABASE_URL must not use a default password in production."
            )
        return self
