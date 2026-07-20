from app.tasks.celery_app import celery_app

@celery_app.task
def run_prediction_job():
    return {"status": "prediction job triggered"}
