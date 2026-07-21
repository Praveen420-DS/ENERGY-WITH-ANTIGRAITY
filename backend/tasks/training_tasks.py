from tasks.celery_app import celery_app
@celery_app.task
def run_training_job():
    return {"status": "training job triggered"}
