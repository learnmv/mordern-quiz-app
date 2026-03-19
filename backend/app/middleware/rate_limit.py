"""Rate limiting middleware for API protection."""
import time
import logging
from fastapi import Request, HTTPException
from typing import Optional, Dict, Any
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Redis-based rate limiter with sliding window algorithm."""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limit using sliding window.

        Args:
            key: Unique identifier for the rate limit bucket
            limit: Maximum number of requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (allowed, metadata) where metadata contains rate limit info
        """
        try:
            r = await self._get_redis()
            now = time.time()
            window_start = now - window

            # Remove old entries outside the window
            await r.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            current = await r.zcard(key)

            if current >= limit:
                # Get oldest entry to calculate retry after
                oldest = await r.zrange(key, 0, 0, withscores=True)
                retry_after = int(oldest[0][1] + window - now) if oldest else window

                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset": int(now + window),
                    "retry_after": retry_after,
                    "window": window
                }

            # Add current request
            await r.zadd(key, {str(now): now})
            await r.expire(key, window)

            return True, {
                "limit": limit,
                "remaining": limit - current - 1,
                "reset": int(now + window),
                "retry_after": 0,
                "window": window
            }

        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open if Redis is unavailable
            return True, {
                "limit": limit,
                "remaining": limit - 1,
                "reset": int(time.time() + window),
                "retry_after": 0,
                "window": window,
                "error": str(e)
            }

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting based on endpoint and auth status.

    Different endpoints have different rate limits:
    - /api/generate-quiz: 10 requests per minute (expensive operation)
    - /api/generate-diagram-quiz: 10 requests per minute (expensive operation)
    - /api/generate-quiz-stream: 5 requests per minute (very expensive)
    - Other /api/*: 100 requests per minute
    """
    if not settings.rate_limit_enabled:
        return await call_next(request)

    path = request.url.path
    user_id = getattr(request.state, 'user_id', None)
    client_ip = request.client.host if request.client else 'unknown'

    # Determine rate limit based on endpoint
    limiter = get_rate_limiter()

    # Very expensive endpoints
    if path in ["/api/generate-quiz-stream"]:
        key = f"rate_limit:stream:{user_id or client_ip}"
        limit = 5  # 5 requests per minute
        window = 60
    # Expensive endpoints
    elif path in ["/api/generate-quiz", "/api/generate-diagram-quiz"]:
        key = f"rate_limit:generate:{user_id or client_ip}"
        limit = settings.rate_limit_generate
        window = 60
    # General API endpoints
    elif path.startswith("/api/"):
        key = f"rate_limit:api:{user_id or client_ip}"
        limit = settings.rate_limit_default
        window = 60
    else:
        # No rate limiting for non-API paths
        return await call_next(request)

    # Check rate limit
    allowed, headers = await limiter.is_allowed(key, limit, window)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": headers["retry_after"],
                "limit": headers["limit"],
                "window": headers["window"]
            },
            headers={
                "Retry-After": str(headers["retry_after"]),
                "X-RateLimit-Limit": str(headers["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(headers["reset"])
            }
        )

    # Process request
    response = await call_next(request)

    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(headers["limit"])
    response.headers["X-RateLimit-Remaining"] = str(headers["remaining"])
    response.headers["X-RateLimit-Reset"] = str(headers["reset"])

    return response


class RateLimitDecorator:
    """Decorator for rate limiting specific functions."""

    def __init__(self, limit: int = 100, window: int = 60, key_func=None):
        self.limit = limit
        self.window = window
        self.key_func = key_func or (lambda *args, **kwargs: "default")
        self._limiter = None

    async def __call__(self, func):
        async def wrapper(*args, **kwargs):
            if self._limiter is None:
                self._limiter = get_rate_limiter()

            key = f"rate_limit:decorator:{self.key_func(*args, **kwargs)}"
            allowed, headers = await self._limiter.is_allowed(key, self.limit, self.window)

            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Retry after {headers['retry_after']} seconds."
                )

            return await func(*args, **kwargs)

        return wrapper
