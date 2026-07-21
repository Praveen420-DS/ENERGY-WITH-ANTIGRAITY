from celery import Celery
from app.config import Settings

settings = Settings()

# Use environment-configured Celery/Redis URLs (fall back to sensible defaults)
broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery("backend_tasks", broker=broker_url, backend=result_backend,)
celery_app.conf.imports = (
    "tasks.prediction_tasks",
    "tasks.training_tasks",
    "tasks.report_tasks",
    "tasks.notification_tasks",
)

