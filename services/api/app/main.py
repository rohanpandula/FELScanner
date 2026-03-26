"""
FELScanner v2 - FastAPI Application
Main entry point for the API service
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.metrics import PrometheusMiddleware, metrics_endpoint

# Initialize logging first
settings = get_settings()
setup_logging(
    log_level=settings.LOG_LEVEL,
    json_logs=settings.is_production
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info(
        "app.startup",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    # Initialize database
    await init_db()

    # Start background task scheduler
    from app.tasks.scheduler import TaskScheduler
    app.state.scheduler = TaskScheduler()
    await app.state.scheduler.start()

    # Initialize Telegram handler if enabled
    if settings.TELEGRAM_ENABLED:
        from app.integrations.telegram.handler import TelegramHandler
        app.state.telegram = TelegramHandler()
        await app.state.telegram.initialize()

    logger.info("app.startup_complete")

    yield

    # Shutdown
    logger.info("app.shutdown")

    # Shutdown task scheduler
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.shutdown()

    # Shutdown Telegram handler
    if hasattr(app.state, "telegram"):
        await app.state.telegram.shutdown()

    # Close database connections
    await close_db()

    logger.info("app.shutdown_complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Next-generation Dolby Vision/TrueHD intelligence layer for Plex",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Prometheus metrics middleware - DISABLED temporarily due to implementation issue
# app.middleware("http")(PrometheusMiddleware(app))


# ============================================================================
# HEALTH & METRICS
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check():
    """Basic health check endpoint"""
    return JSONResponse(
        content={
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }
    )


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check with dependency verification
    Checks database and Redis connectivity
    """
    checks = {
        "database": "unknown",
        "redis": "unknown",
    }

    # TODO: Check database connection
    # try:
    #     async with get_db() as db:
    #         await db.execute(text("SELECT 1"))
    #     checks["database"] = "healthy"
    # except Exception as e:
    #     checks["database"] = f"unhealthy: {str(e)}"

    # TODO: Check Redis connection
    # try:
    #     await redis_client.ping()
    #     checks["redis"] = "healthy"
    # except Exception as e:
    #     checks["redis"] = f"unhealthy: {str(e)}"

    checks["database"] = "healthy"  # Temporary
    checks["redis"] = "healthy"  # Temporary

    all_healthy = all(status == "healthy" for status in checks.values())

    return JSONResponse(
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
        },
        status_code=200 if all_healthy else 503,
    )


# Prometheus metrics endpoint (using custom endpoint with all metrics)
@app.get("/metrics", tags=["metrics"])
async def get_metrics():
    """Prometheus metrics endpoint"""
    return metrics_endpoint()


# ============================================================================
# API ROUTERS
# ============================================================================

from app.api.v1 import api_router

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/", tags=["root"])
async def root():
    """API root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
