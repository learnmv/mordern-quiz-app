"""Circuit breaker pattern implementation for Ollama API calls."""
import time
import logging
import functools
from enum import Enum
from typing import Callable, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation - requests pass through
    OPEN = "open"          # Failure threshold reached - requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: int = 60          # Seconds before attempting recovery
    half_open_max_calls: int = 3        # Max calls in half-open state
    success_threshold: int = 2          # Successes needed to close circuit


class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Example:
        breaker = CircuitBreaker("ollama", failure_threshold=5, recovery_timeout=60)

        @breaker
        async def call_ollama_api(prompt: str) -> dict:
            # API call here
            pass

        try:
            result = await call_ollama_api("Generate a question...")
        except CircuitBreakerOpen:
            # Handle circuit open - service unavailable
            pass
    """

    _instances: dict = {}  # Singleton instances by name

    def __new__(cls, name: str, *args, **kwargs):
        """Ensure singleton pattern per name."""
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        success_threshold: int = 2
    ):
        if hasattr(self, '_initialized'):
            return

        self.name = name
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            success_threshold=success_threshold
        )

        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._initialized = True

        logger.info(f"Circuit breaker '{name}' initialized (threshold={failure_threshold}, timeout={recovery_timeout}s)")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    def _can_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.config.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.config.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' closed - service recovered")
                self._reset()
        else:
            self._failures = max(0, self._failures - 1)

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker '{self.name}' opened - recovery failed")
            self._state = CircuitState.OPEN
            self._half_open_calls = 0
        elif self._failures >= self.config.failure_threshold:
            logger.warning(f"Circuit breaker '{self.name}' opened - failure threshold reached")
            self._state = CircuitState.OPEN

    def _reset(self) -> None:
        """Reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._successes = 0
        self._half_open_calls = 0
        self._last_failure_time = None

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: Any exception from the wrapped function
        """
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state == CircuitState.OPEN:
            if self._can_attempt_reset():
                logger.info(f"Circuit breaker '{self.name}' half-open - testing recovery")
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._successes = 0
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN - {self.name} service unavailable"
                )

        # Limit calls in half-open state
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is HALF_OPEN - max test calls reached"
                )
            self._half_open_calls += 1

        # Execute the function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap a function with circuit breaker."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)
        return wrapper

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failures,
            "successes": self._successes,
            "last_failure_time": self._last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "half_open_max_calls": self.config.half_open_max_calls,
                "success_threshold": self.config.success_threshold,
            }
        }


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get existing circuit breaker by name."""
    return CircuitBreaker._instances.get(name)


def reset_circuit_breaker(name: str) -> bool:
    """Reset a circuit breaker to closed state.

    Returns:
        True if circuit breaker existed and was reset
    """
    breaker = CircuitBreaker._instances.get(name)
    if breaker:
        breaker._reset()
        logger.info(f"Circuit breaker '{name}' manually reset")
        return True
    return False


def get_all_circuit_breakers() -> dict:
    """Get all circuit breaker instances."""
    return {name: breaker.get_stats() for name, breaker in CircuitBreaker._instances.items()}


# Create default circuit breaker for Ollama
ollama_circuit_breaker = CircuitBreaker(
    name="ollama",
    failure_threshold=5,
    recovery_timeout=60,
    half_open_max_calls=3,
    success_threshold=2
)
