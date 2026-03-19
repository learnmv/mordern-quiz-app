"""Business metrics for monitoring and analytics."""
import time
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

# Try to import prometheus client
try:
    from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("prometheus_client not installed, metrics will be disabled")

logger = logging.getLogger(__name__)

# Registry for metrics
_registry = None

# Metrics definitions
_quiz_generation_total = None
_quiz_generation_duration = None
_quiz_completion_rate = None
_user_engagement = None
_active_users = None
_cache_hit_rate = None


def init_metrics():
    """Initialize Prometheus metrics."""
    global _registry, _quiz_generation_total, _quiz_generation_duration
    global _quiz_completion_rate, _user_engagement, _active_users, _cache_hit_rate

    if not PROMETHEUS_AVAILABLE:
        return

    _registry = CollectorRegistry()

    # Quiz generation metrics
    _quiz_generation_total = Counter(
        'quiz_generation_total',
        'Total quiz generations',
        ['grade', 'topic', 'difficulty', 'source'],  # source: cache, ollama
        registry=_registry
    )

    _quiz_generation_duration = Histogram(
        'quiz_generation_duration_seconds',
        'Time spent generating quizzes',
        ['grade', 'difficulty', 'source'],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
        registry=_registry
    )

    # Quiz completion metrics
    _quiz_completion_rate = Gauge(
        'quiz_completion_rate',
        'Percentage of quizzes completed',
        ['grade', 'difficulty'],
        registry=_registry
    )

    # User engagement metrics
    _user_engagement = Counter(
        'user_engagement_total',
        'User engagement events',
        ['event_type'],  # question_answered, quiz_started, quiz_completed, etc.
        registry=_registry
    )

    _active_users = Gauge(
        'active_users',
        'Number of currently active users',
        [],
        registry=_registry
    )

    # Cache metrics
    _cache_hit_rate = Gauge(
        'cache_hit_rate',
        'Cache hit rate percentage',
        ['cache_type'],  # memory, database
        registry=_registry
    )

    # Service info
    Info('quiz_app_info', 'Quiz application information', registry=_registry)

    logger.info("Prometheus metrics initialized")


def record_quiz_generation(
    grade: str,
    topic: str,
    difficulty: str,
    source: str = "ollama"
) -> None:
    """Record a quiz generation event.

    Args:
        grade: Grade level
        topic: Math topic
        difficulty: Difficulty level
        source: Source of quiz (cache, ollama)
    """
    if _quiz_generation_total:
        _quiz_generation_total.labels(
            grade=grade,
            topic=topic,
            difficulty=difficulty,
            source=source
        ).inc()

    logger.debug(
        f"Quiz generated: {grade}/{topic}/{difficulty} from {source}",
        extra={
            "grade": grade,
            "topic": topic,
            "difficulty": difficulty,
            "source": source
        }
    )


@contextmanager
def timed_quiz_generation(grade: str, difficulty: str, source: str = "ollama"):
    """Context manager to time quiz generation.

    Args:
        grade: Grade level
        difficulty: Difficulty level
        source: Source of quiz

    Example:
        with timed_quiz_generation("6", "medium", "ollama"):
            quiz_data = await generate_quiz(...)
    """
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        if _quiz_generation_duration:
            _quiz_generation_duration.labels(
                grade=grade,
                difficulty=difficulty,
                source=source
            ).observe(duration)


def record_quiz_completion(grade: str, difficulty: str, completed: bool) -> None:
    """Record quiz completion status.

    Args:
        grade: Grade level
        difficulty: Difficulty level
        completed: Whether quiz was completed
    """
    # This is a gauge that should be updated based on actual completion rates
    # For now, we just record the event
    if completed:
        record_user_engagement("quiz_completed")
    else:
        record_user_engagement("quiz_abandoned")


def record_user_engagement(event_type: str) -> None:
    """Record a user engagement event.

    Args:
        event_type: Type of engagement event
            - question_answered
            - quiz_started
            - quiz_completed
            - quiz_abandoned
            - hint_used
            - explanation_viewed
    """
    if _user_engagement:
        _user_engagement.labels(event_type=event_type).inc()

    logger.debug(f"User engagement: {event_type}", extra={"event_type": event_type})


def set_active_users(count: int) -> None:
    """Set the number of active users.

    Args:
        count: Number of active users
    """
    if _active_users:
        _active_users.set(count)


def set_cache_hit_rate(cache_type: str, rate: float) -> None:
    """Set cache hit rate.

    Args:
        cache_type: Type of cache (memory, database)
        rate: Hit rate as percentage (0-100)
    """
    if _cache_hit_rate:
        _cache_hit_rate.labels(cache_type=cache_type).set(rate)


class MetricsCollector:
    """Collector for custom business metrics."""

    def __init__(self):
        self._custom_metrics: Dict[str, Any] = {}

    def record(self, metric_name: str, value: float, labels: Optional[Dict] = None) -> None:
        """Record a custom metric value.

        Args:
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels
        """
        key = f"{metric_name}:{labels or {}}"
        self._custom_metrics[key] = {
            "value": value,
            "labels": labels or {},
            "timestamp": time.time()
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get all custom metrics."""
        return self._custom_metrics


# Global metrics collector
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics_collector


def get_prometheus_metrics() -> str:
    """Get Prometheus formatted metrics.

    Returns:
        Metrics in Prometheus text format
    """
    if not PROMETHEUS_AVAILABLE or _registry is None:
        return "# Prometheus metrics not available\n"

    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest(_registry).decode('utf-8')
