from tasks.celery_app import celery_app
@celery_app.task
def generate_report_task():
    return {"status": "report generation triggered"}
