from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from contextvars import ContextVar
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from app.config import settings

# Context variable for current session type (primary or replica)
session_type = ContextVar('session_type', default='primary')

# Primary database engine for writes
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Read replica engine (falls back to primary if not configured)
replica_url = getattr(settings, 'database_replica_url', settings.database_url)
replica_engine = create_async_engine(
    replica_url,
    echo=False,
    future=True,
    pool_size=30,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
) if replica_url != settings.database_url else engine

# Session factories
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

ReplicaSessionLocal = async_sessionmaker(
    replica_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions.

    Automatically uses read replica for read operations if configured.
    Use use_replica() context manager to explicitly use replica.
    """
    if session_type.get() == 'replica':
        async with ReplicaSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    else:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


@asynccontextmanager
async def use_replica():
    """Context manager to use read replica for database operations.

    Example:
        async with use_replica():
            # These queries will use the read replica
            result = await db.execute(query)
    """
    token = session_type.set('replica')
    try:
        yield
    finally:
        session_type.reset(token)


@asynccontextmanager
async def use_primary():
    """Context manager to explicitly use primary database.

    Example:
        async with use_primary():
            # These queries will use the primary database
            await db.commit()
    """
    token = session_type.set('primary')
    try:
        yield
    finally:
        session_type.reset(token)


async def get_db_with_fallback() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with automatic fallback from replica to primary.

    Tries replica first, falls back to primary on connection errors.
    """
    try:
        async with ReplicaSessionLocal() as session:
            # Test connection
            await session.execute("SELECT 1")
            async with use_replica():
                yield session
    except Exception:
        # Fallback to primary
        async with AsyncSessionLocal() as session:
            yield session