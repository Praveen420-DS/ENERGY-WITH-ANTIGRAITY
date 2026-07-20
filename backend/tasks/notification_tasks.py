from app.tasks.celery_app import celery_app

@celery_app.task
def send_notification_task(message: str):
    return {"status": "notification sent", "message": message}
