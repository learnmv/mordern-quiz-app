from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, quiz, progress
from app.services.gamification import init_badges
from app.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialize badges
    async with AsyncSessionLocal() as db:
        await init_badges(db)

    yield

    # Shutdown
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


@app.get("/")
async def root():
    return {"message": "Quiz App API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}