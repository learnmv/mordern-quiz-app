"""Request deduplication middleware to prevent duplicate expensive operations."""
import json
import hashlib
import logging
import time
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, Response
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)


class RequestDeduplicator:
    """Deduplicate identical requests within a time window.

    Uses Redis to track request hashes and cache responses.
    """

    def __init__(self, ttl: int = 30, response_ttl: int = 300):
        self.ttl = ttl  # Dedup window in seconds
        self.response_ttl = response_ttl  # How long to cache responses
        self._redis: Optional[redis.Redis] = None
        self._redis_url = settings.redis_url

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def generate_request_hash(
        self,
        method: str,
        path: str,
        body: bytes,
        user_id: Optional[str] = None
    ) -> str:
        """Generate unique hash for request.

        Args:
            method: HTTP method
            path: Request path
            body: Request body bytes
            user_id: Optional user ID

        Returns:
            SHA256 hash of request
        """
        # Normalize the content
        content = f"{method}:{path}:{body.decode() if body else ''}:{user_id or 'anon'}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def is_duplicate(self, request_hash: str) -> bool:
        """Check if this is a duplicate request.

        Uses Redis SET with NX (only if not exists) to atomically check and set.

        Args:
            request_hash: Hash of the request

        Returns:
            True if this is a duplicate (request already in progress)
        """
        try:
            r = await self._get_redis()
            key = f"dedup:{request_hash}"

            # Try to set key with NX (only if not exists)
            result = await r.set(key, str(time.time()), nx=True, ex=self.ttl)

            # If result is None, key already exists (duplicate)
            return result is None

        except Exception as e:
            logger.error(f"Deduplication check error: {e}")
            # Fail open - allow request if Redis is down
            return False

    async def get_cached_response(self, request_hash: str) -> Optional[Dict]:
        """Get cached response for duplicate request.

        Args:
            request_hash: Hash of the request

        Returns:
            Cached response data or None
        """
        try:
            r = await self._get_redis()
            key = f"dedup:response:{request_hash}"
            cached = await r.get(key)
            return json.loads(cached) if cached else None

        except Exception as e:
            logger.error(f"Get cached response error: {e}")
            return None

    async def cache_response(self, request_hash: str, response: dict, ttl: int = None) -> None:
        """Cache response for potential duplicates.

        Args:
            request_hash: Hash of the request
            response: Response data to cache
            ttl: Time to live in seconds (defaults to self.response_ttl)
        """
        try:
            r = await self._get_redis()
            key = f"dedup:response:{request_hash}"
            await r.setex(key, ttl or self.response_ttl, json.dumps(response))

        except Exception as e:
            logger.error(f"Cache response error: {e}")

    async def release_dedup_lock(self, request_hash: str) -> None:
        """Release the deduplication lock early.

        Call this after response is cached to allow new requests.

        Args:
            request_hash: Hash of the request
        """
        try:
            r = await self._get_redis()
            key = f"dedup:{request_hash}"
            await r.delete(key)

        except Exception as e:
            logger.error(f"Release dedup lock error: {e}")

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global deduplicator instance
_deduplicator: Optional[RequestDeduplicator] = None


def get_deduplicator() -> RequestDeduplicator:
    """Get or create global deduplicator instance."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = RequestDeduplicator()
    return _deduplicator


async def dedup_middleware(request: Request, call_next):
    """Deduplicate identical POST/PUT requests.

    Only applies to expensive operations like quiz generation.
    """
    # Only dedup POST/PUT requests
    if request.method not in ["POST", "PUT"]:
        return await call_next(request)

    # Only dedup specific expensive endpoints
    dedup_paths = [
        "/api/generate-quiz",
        "/api/generate-diagram-quiz",
        "/api/generate-quiz-stream"
    ]

    if request.url.path not in dedup_paths:
        return await call_next(request)

    dedup = get_deduplicator()

    # Read request body
    body = await request.body()
    user_id = getattr(request.state, 'user_id', None)

    # Generate request hash
    request_hash = dedup.generate_request_hash(
        request.method,
        request.url.path,
        body,
        user_id
    )

    # Check for duplicate
    if await dedup.is_duplicate(request_hash):
        # Return cached response if available
        cached = await dedup.get_cached_response(request_hash)
        if cached:
            logger.info(f"Returning cached response for {request.url.path}")
            return JSONResponse(
                content=cached,
                headers={"X-Dedup": "true", "X-Dedup-Cached": "true"}
            )

        # Request in progress but no cached response yet
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Duplicate request in progress",
                "message": "An identical request is currently being processed. Please wait and retry."
            },
            headers={"X-Dedup": "true", "Retry-After": "5"}
        )

    # Process request
    try:
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            try:
                response_data = json.loads(response_body)
                await dedup.cache_response(request_hash, response_data)
            except json.JSONDecodeError:
                pass  # Don't cache non-JSON responses

            # Release lock early
            await dedup.release_dedup_lock(request_hash)

            # Return new response
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        return response

    except Exception as e:
        # Release lock on error
        await dedup.release_dedup_lock(request_hash)
        raise
