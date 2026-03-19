import time
import logging
import uuid
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, quiz, progress, health, admin
from app.services.gamification import init_badges
from app.database import AsyncSessionLocal
from app.tasks.queue import start_all_queues, stop_all_queues
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.dedup import dedup_middleware
from app.logging_config import setup_logging, set_correlation_id, correlation_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Setup logging
    setup_logging(level=logging.INFO, json_format=True)

    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize badges
    async with AsyncSessionLocal() as db:
        await init_badges(db)

    # Start background task queues
    await start_all_queues()

    logger = logging.getLogger(__name__)
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down")
    await stop_all_queues()
    await engine.dispose()


app = FastAPI(
    title="Quiz App API",
    description="FastAPI backend for the Quiz App",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(quiz.router)
app.include_router(progress.router)
app.include_router(health.router)
app.include_router(admin.router)


# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Set correlation ID for request tracing."""
    # Get or generate correlation ID
    cid = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
    token = correlation_id.set(cid)

    logger = logging.getLogger('app')
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else None
        }
    )

    try:
        response = await call_next(request)
        response.headers['X-Correlation-ID'] = cid
        return response
    except Exception as e:
        logger.exception("Request failed", extra={"error": str(e)})
        raise
    finally:
        logger.info(
            f"Request completed: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path
            }
        )
        correlation_id.reset(token)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_handler(request: Request, call_next):
    """Apply rate limiting."""
    return await rate_limit_middleware(request, call_next)


# Request deduplication middleware
@app.middleware("http")
async def dedup_handler(request: Request, call_next):
    """Apply request deduplication."""
    return await dedup_middleware(request, call_next)


# Performance metrics middleware
@app.middleware("http")
async def add_metrics(request: Request, call_next):
    """Add request timing metrics."""
    start_time = time.time()

    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Add timing header
    response.headers["X-Response-Time"] = f"{duration:.3f}s"

    # Log slow requests (> 1 second)
    if duration > 1.0:
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Slow request: {request.method} {request.url.path} took {duration:.3f}s",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration": duration
            }
        )

    return response


@app.get("/")
async def root():
    return {"message": "Quiz App API", "version": "1.0.0"}


# Legacy health endpoint (redirects to new health router)
@app.get("/health")
async def legacy_health_check():
    return {"status": "healthy"}


# Legacy metrics endpoint (redirects to new health router)
@app.get("/metrics")
async def legacy_metrics():
    """Get application metrics."""
    from app.tasks.queue import get_all_queue_stats
    from app.utils.cache import get_cache_stats
    from app.utils.circuit_breaker import get_all_circuit_breakers

    return {
        "queues": get_all_queue_stats(),
        "cache": get_cache_stats(),
        "circuit_breakers": get_all_circuit_breakers()
    }