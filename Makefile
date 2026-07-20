# ========================
# Makefile — Common Commands
# ========================

.PHONY: build run stop dev test clean logs

# --- Docker ---
build:
	docker compose -f docker/docker-compose.yml build

run:
	docker compose -f docker/docker-compose.yml up -d

stop:
	docker compose -f docker/docker-compose.yml down

dev:
	docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up --build

logs:
	docker compose -f docker/docker-compose.yml logs -f

# --- Backend ---
backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test:
	cd backend && pytest tests/ -v

# --- Frontend ---
frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

# --- ML ---
ml-train:
	cd ml_service && python -m pipelines.training

# --- Cleanup ---
clean:
	docker compose -f docker/docker-compose.yml down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf frontend/node_modules frontend/dist
