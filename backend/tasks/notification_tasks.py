from tasks.celery_app import celery_app
def send_notification_task(message: str):
    return {"status": "notification sent", "message": message}
