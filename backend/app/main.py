from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import connect_db, disconnect_db
from app.routers import auth, users, meters, energy, predictions, anomalies, alerts, models, system

settings = Settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.on_event("startup")
async def startup_event():
    await connect_db(settings.database_url)

@app.on_event("shutdown")
async def shutdown_event():
    await disconnect_db()

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(meters.router, prefix="/api/meters", tags=["meters"])
app.include_router(energy.router, prefix="/api/energy", tags=["energy"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(anomalies.router, prefix="/api/anomalies", tags=["anomalies"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
