"""Celery application with JSON-only message serialization."""

from celery import Celery

from app.config import Settings

settings = Settings()
broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery(
    "backend_tasks",
    broker=broker_url,
    backend=result_backend,
)
celery_app.conf.imports = (
    "tasks.prediction_tasks",
    "tasks.training_tasks",
    "tasks.report_tasks",
    "tasks.notification_tasks",
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
)
