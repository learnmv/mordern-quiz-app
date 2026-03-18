"""Background tasks module."""
from app.tasks.question_generator import (
    pregenerate_popular_questions,
    pregenerate_single_topic,
    generate_and_store_questions,
    get_cache_count,
    POPULAR_COMBINATIONS,
    MIN_CACHE_THRESHOLD,
)
from app.tasks.queue import (
    TaskQueue,
    Task,
    TaskStatus,
    get_queue,
    start_all_queues,
    stop_all_queues,
    generate_questions_task,
    question_generation_queue,
)

__all__ = [
    # Question generator
    "pregenerate_popular_questions",
    "pregenerate_single_topic",
    "generate_and_store_questions",
    "get_cache_count",
    "POPULAR_COMBINATIONS",
    "MIN_CACHE_THRESHOLD",
    # Queue
    "TaskQueue",
    "Task",
    "TaskStatus",
    "get_queue",
    "start_all_queues",
    "stop_all_queues",
    "generate_questions_task",
    "question_generation_queue",
]
