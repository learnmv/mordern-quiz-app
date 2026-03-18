"""Utility modules."""
from app.utils.cache import (
    cached,
    cache_get,
    cache_set,
    cache_delete,
    cache_clear,
    invalidate_cache_pattern,
    get_cache_stats,
    reset_cache_stats,
)
from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    get_circuit_breaker,
    reset_circuit_breaker,
    get_all_circuit_breakers,
    ollama_circuit_breaker,
)

__all__ = [
    # Cache
    "cached",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_clear",
    "invalidate_cache_pattern",
    "get_cache_stats",
    "reset_cache_stats",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "get_circuit_breaker",
    "reset_circuit_breaker",
    "get_all_circuit_breakers",
    "ollama_circuit_breaker",
]
