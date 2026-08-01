import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from routers import flares, cme, geomagnetic, predictions, solar, alerts
from routers.auth import router as auth_router
from services.cache import init_db
from services.ml_engine import MLEngine
from services.auth_service import init_users_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ml_engine = MLEngine()
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 Starting Solar Flare Prediction API...")
    await init_db()
    await init_users_table()
    await ml_engine.train()
    app.state.ml_engine = ml_engine

    # Re-train model every 6 hours
    scheduler.add_job(ml_engine.train, "interval", hours=6, id="retrain_model")
    scheduler.start()
    logger.info("✅ ML Engine trained and scheduler started.")
    yield
    scheduler.shutdown()
    logger.info("🛑 Server shut down.")

app = FastAPI(
    title="Solar Flare & Space Weather Prediction API",
    description="Real-time space weather data and ML-based solar flare predictions.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins so the frontend (Vercel) can call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth_router,       prefix="/api", tags=["Auth"])
app.include_router(flares.router,     prefix="/api", tags=["Solar Flares"])
app.include_router(cme.router,        prefix="/api", tags=["CME"])
app.include_router(geomagnetic.router,prefix="/api", tags=["Geomagnetic"])
app.include_router(predictions.router,prefix="/api", tags=["Predictions"])
app.include_router(solar.router,      prefix="/api", tags=["Solar Wind"])
app.include_router(alerts.router,     prefix="/api", tags=["Alerts"])

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Solar Flare Prediction API", "version": "1.0.0"}

@app.get("/")
async def root():
    return {
        "message": "Solar Flare & Space Weather Prediction API",
        "docs": "/docs",
        "health": "/health"
    }
