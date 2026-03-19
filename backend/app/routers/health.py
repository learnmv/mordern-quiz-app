"""Health check endpoints for monitoring and Kubernetes probes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Any
import httpx
import redis.asyncio as redis

from app.database import get_db, engine
from app.config import settings
from app.tasks.queue import get_all_queue_stats
from app.services.quiz_generator import get_cache_metrics
from app.utils.cache import get_cache_stats
from app.utils.circuit_breaker import get_all_circuit_breakers

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness_probe():
    """Kubernetes liveness probe - is the app running?

    Returns 200 if the application is alive.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "quiz-app-api"
    }


@router.get("/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Kubernetes readiness probe - is the app ready to serve traffic?

    Checks:
    - Database connectivity
    - Redis connectivity
    - Ollama availability (optional - doesn't fail if Ollama is down)

    Returns 200 if ready, 503 if not ready.
    """
    checks: Dict[str, Any] = {}
    healthy = True

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}
        healthy = False

    # Redis check
    try:
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        checks["redis"] = {"status": "ok"}
    except Exception as e:
        checks["redis"] = {"status": "error", "message": str(e)}
        healthy = False

    # Ollama check (optional - don't fail if Ollama is down)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=5.0
            )
            if response.status_code == 200:
                checks["ollama"] = {"status": "ok"}
            else:
                checks["ollama"] = {
                    "status": "degraded",
                    "message": f"HTTP {response.status_code}"
                }
    except Exception as e:
        checks["ollama"] = {
            "status": "unavailable",
            "message": str(e)
        }

    if not healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

    return {
        "status": "ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/startup")
async def startup_probe():
    """Kubernetes startup probe - is the app started?

    Similar to liveness but used during startup.
    """
    return {
        "status": "started",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    lines = []

    # Cache metrics
    cache_stats = get_cache_stats()
    lines.append(f"# HELP quiz_cache_hits_total Total cache hits")
    lines.append(f"# TYPE quiz_cache_hits_total counter")
    lines.append(f'quiz_cache_hits_total {cache_stats.get("hits", 0)}')

    lines.append(f"# HELP quiz_cache_misses_total Total cache misses")
    lines.append(f"# TYPE quiz_cache_misses_total counter")
    lines.append(f'quiz_cache_misses_total {cache_stats.get("misses", 0)}')

    lines.append(f"# HELP quiz_cache_hit_rate Cache hit rate")
    lines.append(f"# TYPE quiz_cache_hit_rate gauge")
    lines.append(f'quiz_cache_hit_rate {cache_stats.get("hit_rate", 0)}')

    lines.append(f"# HELP quiz_cache_size Current cache size")
    lines.append(f"# TYPE quiz_cache_size gauge")
    lines.append(f'quiz_cache_size {cache_stats.get("size", 0)}')

    # Question cache metrics
    q_cache_stats = get_cache_metrics()
    lines.append(f"# HELP quiz_question_cache_hits Question cache hits")
    lines.append(f"# TYPE quiz_question_cache_hits counter")
    lines.append(f'quiz_question_cache_hits {q_cache_stats.get("hits", 0)}')

    lines.append(f"# HELP quiz_question_cache_misses Question cache misses")
    lines.append(f"# TYPE quiz_question_cache_misses counter")
    lines.append(f'quiz_question_cache_misses {q_cache_stats.get("misses", 0)}')

    # Queue metrics
    queue_stats = get_all_queue_stats()
    for queue_name, stats in queue_stats.items():
        lines.append(f"# HELP quiz_queue_tasks Queue tasks by status")
        lines.append(f"# TYPE quiz_queue_tasks gauge")
        for status_key, count in stats.get('by_status', {}).items():
            lines.append(f'quiz_queue_tasks{{queue="{queue_name}",status="{status_key}"}} {count}')

        lines.append(f"# HELP quiz_queue_size Queue size")
        lines.append(f"# TYPE quiz_queue_size gauge")
        lines.append(f'quiz_queue_size{{queue="{queue_name}"}} {stats.get("queue_size", 0)}')

    # Circuit breaker metrics
    cb_stats = get_all_circuit_breakers()
    for cb_name, stats in cb_stats.items():
        lines.append(f"# HELP quiz_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half_open)")
        lines.append(f"# TYPE quiz_circuit_breaker_state gauge")
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        state_value = state_map.get(stats.get("state", "closed"), 0)
        lines.append(f'quiz_circuit_breaker_state{{name="{cb_name}"}} {state_value}')

        lines.append(f"# HELP quiz_circuit_breaker_failures Circuit breaker failure count")
        lines.append(f"# TYPE quiz_circuit_breaker_failures counter")
        lines.append(f'quiz_circuit_breaker_failures{{name="{cb_name}"}} {stats.get("failures", 0)}')

    return "\n".join(lines)


@router.get("/status")
async def detailed_status(db: AsyncSession = Depends(get_db)):
    """Detailed status information for debugging.

    Returns comprehensive information about the application state.
    """
    status_info = {
        "service": "quiz-app-api",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }

    # Database status
    try:
        result = await db.execute(text("SELECT version()"))
        version = result.scalar()
        status_info["components"]["database"] = {
            "status": "connected",
            "version": version.split()[0] if version else "unknown"
        }
    except Exception as e:
        status_info["components"]["database"] = {
            "status": "error",
            "error": str(e)
        }

    # Redis status
    try:
        r = redis.from_url(settings.redis_url)
        info = await r.info()
        await r.close()
        status_info["components"]["redis"] = {
            "status": "connected",
            "version": info.get("redis_version", "unknown"),
            "used_memory": info.get("used_memory_human", "unknown")
        }
    except Exception as e:
        status_info["components"]["redis"] = {
            "status": "error",
            "error": str(e)
        }

    # Ollama status
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.ollama_base_url}/api/tags",
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                status_info["components"]["ollama"] = {
                    "status": "connected",
                    "available_models": models,
                    "configured_model": settings.ollama_model
                }
            else:
                status_info["components"]["ollama"] = {
                    "status": "error",
                    "http_status": response.status_code
                }
    except Exception as e:
        status_info["components"]["ollama"] = {
            "status": "error",
            "error": str(e)
        }

    # Application metrics
    status_info["metrics"] = {
        "cache": get_cache_stats(),
        "question_cache": get_cache_metrics(),
        "queues": get_all_queue_stats(),
        "circuit_breakers": get_all_circuit_breakers()
    }

    return status_info
