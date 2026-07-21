# AI-Based Energy Consumption Prediction System

An intelligent, data-driven system that leverages machine learning to accurately predict short-term and medium-term energy consumption — enabling proactive energy management, cost optimization, and sustainable resource allocation.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite |
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL 16 |
| ML Engine | Python + XGBoost |
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

# Backend
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload

# ML Service
cd ml_service && pip install -r requirements.txt
```

## Documentation
- [System Design](docs/system_design.md)
- [API Reference](docs/api_reference.md)
- [Deployment Guide](docs/deployment_guide.md)

## License
This project is developed as a final-year engineering project.
