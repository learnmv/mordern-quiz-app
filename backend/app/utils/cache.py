"""Caching utilities for the quiz application."""
import json
import hashlib
import functools
import logging
from typing import Any, Optional, Callable
from datetime import timedelta

# Simple in-memory cache (for production, use Redis)
_cache: dict = {}
_cache_ttl: dict = {}

logger = logging.getLogger(__name__)


def _generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate a cache key from prefix and arguments."""
    key_parts = [prefix]
    key_parts.extend(str(arg) for arg in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache."""
    from datetime import datetime

    if key not in _cache:
        return None

    # Check if expired
    if key in _cache_ttl:
        if datetime.now() > _cache_ttl[key]:
            del _cache[key]
            del _cache_ttl[key]
            return None

    return _cache[key]


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Set a value in cache with TTL."""
    from datetime import datetime, timedelta

    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=ttl_seconds)


def cache_delete(key: str) -> None:
    """Delete a value from cache."""
    if key in _cache:
        del _cache[key]
    if key in _cache_ttl:
        del _cache_ttl[key]


def cache_clear() -> None:
    """Clear all cached values."""
    _cache.clear()
    _cache_ttl.clear()


def cached(key_prefix: str, ttl: int = 300):
    """Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds (default 5 minutes)

    Example:
        @cached("user_progress", ttl=60)
        async def get_user_progress(db: AsyncSession, user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(key_prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {key_prefix}")
                return cached_value

            # Call the function
            result = await func(*args, **kwargs)

            # Store in cache
            cache_set(cache_key, result, ttl)
            logger.debug(f"Cache set for {key_prefix}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(key_prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {key_prefix}")
                return cached_value

            # Call the function
            result = func(*args, **kwargs)

            # Store in cache
            cache_set(cache_key, result, ttl)
            logger.debug(f"Cache set for {key_prefix}")

            return result

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate all cache keys matching a pattern.

    Args:
        pattern: String pattern to match (simple substring match)

    Returns:
        Number of keys invalidated
    """
    keys_to_delete = [key for key in _cache.keys() if pattern in key]
    for key in keys_to_delete:
        cache_delete(key)
    return len(keys_to_delete)


class CacheStats:
    """Simple cache statistics tracking."""

    def __init__(self):
        self.hits = 0
        self.misses = 0

    def hit(self):
        self.hits += 1

    def miss(self):
        self.misses += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "size": len(_cache)
        }


# Global cache stats
_cache_stats = CacheStats()


def get_cache_stats() -> dict:
    """Get current cache statistics."""
    return _cache_stats.to_dict()


def reset_cache_stats() -> None:
    """Reset cache statistics."""
    _cache_stats.hits = 0
    _cache_stats.misses = 0
