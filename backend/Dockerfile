FROM python:3.12.9-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system app && adduser --system --ingroup app app
COPY --chown=app:app backend/app ./app
COPY --chown=app:app backend/tasks ./tasks
COPY --chown=app:app ml_service/inference.py ./ml_service/inference.py
COPY --chown=app:app ml_service/models ./ml_service/models
COPY --chown=app:app ml_service/pipelines ./ml_service/pipelines
COPY --chown=app:app scripts/week2_feature_engineering.py ./scripts/week2_feature_engineering.py
COPY --chown=app:app scripts/week2_package_production_model.py ./scripts/week2_package_production_model.py
COPY --chown=app:app reports/week2_baseline_metrics.json ./reports/week2_baseline_metrics.json
COPY --chown=app:app reports/week2_advanced_metrics.json ./reports/week2_advanced_metrics.json
COPY --chown=app:app models/production ./models/production
COPY --chown=app:app models/candidates/v2.0.0-electricity ./models/candidates/v2.0.0-electricity
COPY --chown=app:app scripts/phase2_validate_electricity_candidate.py ./scripts/phase2_validate_electricity_candidate.py
ENV PYTHONPATH=/app
ENV LOKY_MAX_CPU_COUNT=1
COPY --chown=app:app backend/alembic ./alembic
COPY --chown=app:app backend/alembic.ini ./alembic.ini
RUN chmod -R a-w /app/app /app/tasks /app/alembic \
    /app/models/production /app/ml_service /app/scripts
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
