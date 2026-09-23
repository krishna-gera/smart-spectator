"""
Smart Spectator Backend
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import auth, devices, pairing, monitoring, events, alerts, websocket, frames
from app.core.config import settings
from app.core.logging import configure_logging
from app.database.session import engine, Base

log = structlog.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    configure_logging()
    log.info("Smart Spectator backend starting", env=settings.APP_ENV)

    # Create tables (dev only — use alembic in prod)
    if settings.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("Database tables created/verified")

    yield

    log.info("Smart Spectator backend shutting down")


app = FastAPI(
    title="Smart Spectator API",
    description="Intelligent visual monitoring platform — backend API.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── Middleware ────────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(devices.router, prefix="/devices", tags=["Devices"])
app.include_router(pairing.router, prefix="/pairing", tags=["Pairing"])
app.include_router(monitoring.router, prefix="/monitoring", tags=["Monitoring"])
app.include_router(events.router, prefix="/events", tags=["Events"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
app.include_router(frames.router, prefix="/frames", tags=["Frames"])
app.include_router(websocket.router, tags=["WebSocket"])


# ─── Health Checks ────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "smart-spectator-api", "version": "1.0.0"}


@app.get("/health/database", tags=["Health"])
async def health_database():
    from app.database.session import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        log.error("Database health check failed", error=str(e))
        return {"status": "error", "database": "disconnected", "detail": str(e)}, 503


@app.get("/health/ai", tags=["Health"])
async def health_ai():
    from app.services.vision.provider_factory import get_vision_provider
    try:
        provider = get_vision_provider()
        info = await provider.health_check()
        return {"status": "ok", "provider": info}
    except Exception as e:
        log.warning("AI health check failed", error=str(e))
        return {"status": "degraded", "detail": str(e)}
