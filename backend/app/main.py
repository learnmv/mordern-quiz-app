import time
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, quiz, progress
from app.services.gamification import init_badges
from app.database import AsyncSessionLocal
from app.tasks.queue import start_all_queues, stop_all_queues


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize badges
    async with AsyncSessionLocal() as db:
        await init_badges(db)

    # Start background task queues
    await start_all_queues()

    yield

    # Shutdown
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
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Slow request: {request.method} {request.url.path} took {duration:.3f}s"
        )

    return response


@app.get("/")
async def root():
    return {"message": "Quiz App API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Get application metrics."""
    from app.tasks.queue import get_all_queue_stats
    from app.utils.cache import get_cache_stats
    from app.utils.circuit_breaker import get_all_circuit_breakers

    return {
        "queues": get_all_queue_stats(),
        "cache": get_cache_stats(),
        "circuit_breakers": get_all_circuit_breakers()
    }