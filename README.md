# AI-Based Energy Consumption Prediction System

An intelligent, data-driven system that leverages machine learning to accurately predict short-term and medium-term energy consumption — enabling proactive energy management, cost optimization, and sustainable resource allocation.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19 + Vite |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 |
| ML Engine | scikit-learn Random Forest production pipeline |
| Auth | JWT |
| Deployment | Docker + Docker Compose |
| Task Queue | Celery + Redis |
| Reverse Proxy | Nginx |

## Project Structure

```
energy-prediction-system/
├── frontend/          # React SPA
├── backend/           # FastAPI application
├── ml_service/        # ML pipeline (standalone service)
├── docker/            # Container orchestration
├── data/              # Sample/seed data
└── docs/              # Documentation
```

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend/ML development)

### Quick Start
```bash
# Clone the repository
git clone <repo-url>
cd energy-prediction-system

# Copy environment variables
cp .env.example .env

# Start all services
docker compose -f docker/docker-compose.yml up --build
```

### Development
```bash
# Frontend
cd frontend && npm install && npm run dev

# Backend (run from the project root so ML modules are importable)
pip install -r backend/requirements.txt
set PYTHONPATH=%CD%\backend;%CD%
uvicorn app.main:app --reload --port 8000

# ML Service
cd ml_service && pip install -r requirements.txt
```

## Documentation
- [System Design](docs/system_design.md)
- [API Reference](docs/api_reference.md)
- [Deployment Guide](docs/deployment_guide.md)
- [Production Model Card](models/production/v1.0.0/model_card.md)
- [Week 3 Integration Report](reports/week3_integration_report.md)
- [Week 4 Deployment Readiness Report](reports/week4_deployment_readiness_report.md)

## Validated local deployment

```powershell
Copy-Item .env.example .env
# Replace every placeholder secret in .env.
docker compose -f docker/docker-compose.yml up -d --build
Invoke-RestMethod http://localhost/api/predictions/health
```

Open <http://localhost/>. See the deployment guide for migrations, health,
backup/restore, recovery, and production-like override commands.

## License
This project is developed as a final-year engineering project.
