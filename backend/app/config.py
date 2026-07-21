from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    app_name: str = "Energy Prediction System"
    app_version: str = "0.1.0"

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/energy_prediction",
        validation_alias="DATABASE_URL",
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

    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60