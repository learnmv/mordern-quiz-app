"""Task queue for background question generation.

This module provides a simple in-memory task queue for background processing.
For production use, consider using Celery or RQ with Redis.
"""
import asyncio
import logging
import uuid
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents a queued task."""
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 0  # Higher priority = processed first


class TaskQueue:
    """Simple in-memory task queue with async processing.

    Example:
        queue = TaskQueue(max_workers=3)

        # Add a task
        task_id = await queue.add(generate_questions, grade="6", topic="Fractions")

        # Get task status
        task = queue.get_task(task_id)
        print(task.status)
    """

    def __init__(self, max_workers: int = 3, name: str = "default"):
        self.name = name
        self.max_workers = max_workers
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._semaphore = asyncio.Semaphore(max_workers)

    async def start(self) -> None:
        """Start the task queue workers."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting task queue '{self.name}' with {self.max_workers} workers")

        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(), name=f"{self.name}_worker_{i}")
            self._workers.append(worker)

    async def stop(self) -> None:
        """Stop the task queue workers."""
        if not self._running:
            return

        self._running = False
        logger.info(f"Stopping task queue '{self.name}'")

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def add(
        self,
        func: Callable,
        *args,
        priority: int = 0,
        **kwargs
    ) -> str:
        """Add a task to the queue.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            priority: Task priority (higher = processed first)
            **kwargs: Keyword arguments for function

        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority
        )

        self._tasks[task_id] = task
        # PriorityQueue uses lowest first, so negate priority
        await self._queue.put((-priority, task_id, task))

        logger.debug(f"Added task {task_id} to queue '{self.name}' (priority={priority})")
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status as dictionary."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        return {
            "id": task.id,
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "priority": task.priority
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task.

        Returns:
            True if task was cancelled, False if already running/completed
        """
        task = self._tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        statuses = {status: 0 for status in TaskStatus}
        for task in self._tasks.values():
            statuses[task.status] += 1

        return {
            "name": self.name,
            "max_workers": self.max_workers,
            "running": self._running,
            "total_tasks": len(self._tasks),
            "by_status": {k.value: v for k, v in statuses.items()},
            "queue_size": self._queue.qsize()
        }

    async def _worker_loop(self) -> None:
        """Worker loop that processes tasks from the queue."""
        while self._running:
            try:
                # Get task from queue with timeout
                try:
                    priority, task_id, task = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                if task.status == TaskStatus.CANCELLED:
                    continue

                # Process task with semaphore for concurrency control
                async with self._semaphore:
                    await self._process_task(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error in queue '{self.name}': {e}")

    async def _process_task(self, task: Task) -> None:
        """Process a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        logger.debug(f"Processing task {task.id}")

        try:
            result = await task.func(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            logger.debug(f"Task {task.id} completed successfully")
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            logger.error(f"Task {task.id} failed: {e}")
        finally:
            task.completed_at = datetime.now()


# Global task queues
_queues: Dict[str, TaskQueue] = {}


def get_queue(name: str = "default", max_workers: int = 3) -> TaskQueue:
    """Get or create a task queue."""
    if name not in _queues:
        _queues[name] = TaskQueue(max_workers=max_workers, name=name)
    return _queues[name]


async def start_all_queues() -> None:
    """Start all registered task queues."""
    for queue in _queues.values():
        await queue.start()


async def stop_all_queues() -> None:
    """Stop all registered task queues."""
    for queue in _queues.values():
        await queue.stop()


def get_all_queue_stats() -> Dict[str, Dict[str, Any]]:
    """Get statistics for all queues."""
    return {name: queue.get_stats() for name, queue in _queues.items()}


# Specialized task functions for quiz generation
async def generate_questions_task(
    grade: str,
    topic: str,
    difficulty: str,
    count: int = 5
) -> Dict[str, Any]:
    """Background task for generating questions.

    This function is designed to be run in the background task queue.
    """
    from app.database import AsyncSessionLocal
    from app.services.quiz_generator import generate_quiz_with_ollama, store_question

    async with AsyncSessionLocal() as db:
        try:
            quiz_data = await generate_quiz_with_ollama(
                grade=grade,
                topic=topic,
                difficulty=difficulty,
                count=count
            )

            if quiz_data and quiz_data.get('questions'):
                stored_count = 0
                for question in quiz_data['questions']:
                    success = await store_question(db, grade, topic, difficulty, question)
                    if success:
                        stored_count += 1

                return {
                    "success": True,
                    "generated": len(quiz_data['questions']),
                    "stored": stored_count,
                    "grade": grade,
                    "topic": topic,
                    "difficulty": difficulty
                }

            return {
                "success": False,
                "error": "No questions generated",
                "grade": grade,
                "topic": topic,
                "difficulty": difficulty
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "grade": grade,
                "topic": topic,
                "difficulty": difficulty
            }


# Create default queues
question_generation_queue = get_queue("question_generation", max_workers=2)
