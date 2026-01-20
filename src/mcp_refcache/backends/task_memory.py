"""In-memory task execution backend using ThreadPoolExecutor.

Provides async task execution for environments where external
task queues (like Hatchet) are not needed or available.

This backend is suitable for:
- Development and testing
- Single-server deployments
- Tasks that don't require durability

Limitations:
- Tasks are lost on server restart
- No distributed execution
- Memory-bound by result storage
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from mcp_refcache.models import TaskInfo, TaskProgress, TaskStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp_refcache.backends.task_base import ProgressCallback

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_WORKERS = 4
DEFAULT_MAX_TASK_HISTORY = 1000
DEFAULT_TASK_TTL_SECONDS = 86400  # 24 hours


@dataclass
class TaskRecord:
    """Internal record for tracking a task and its result."""

    info: TaskInfo
    result: Any = None
    exception: Exception | None = None
    future: Future[Any] | None = None
    on_progress: ProgressCallback | None = None


class MemoryTaskBackend:
    """In-memory task backend using ThreadPoolExecutor.

    This implementation adapts the pattern from document-mcp's JobManager
    for use with the TaskBackend protocol.

    Thread Safety:
        All public methods are thread-safe. Internal state is protected
        by a threading.Lock.

    Example:
        ```python
        backend = MemoryTaskBackend(max_workers=2)

        def slow_computation(x: int) -> int:
            time.sleep(5)
            return x * 2

        # Submit task
        info = backend.submit(
            task_id="task_123",
            func=slow_computation,
            args=(42,),
            kwargs={},
        )

        # Poll for completion
        while True:
            status = backend.get_status("task_123")
            if status and status.is_terminal:
                break
            time.sleep(0.5)

        # Get result
        result = backend.get_result("task_123")
        print(result)  # 84
        ```
    """

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        max_task_history: int = DEFAULT_MAX_TASK_HISTORY,
        task_ttl_seconds: float = DEFAULT_TASK_TTL_SECONDS,
    ) -> None:
        """Initialize the memory task backend.

        Args:
            max_workers: Maximum concurrent background tasks.
            max_task_history: Maximum tasks to keep in memory.
            task_ttl_seconds: Seconds to keep completed tasks before cleanup.
        """
        self._tasks: dict[str, TaskRecord] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()
        self._cancelled: set[str] = set()

        self.max_workers = max_workers
        self.max_task_history = max_task_history
        self.task_ttl_seconds = task_ttl_seconds

    def _get_executor(self) -> ThreadPoolExecutor:
        """Get or create the thread pool executor (lazy initialization)."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="task_worker",
            )
            logger.info(
                "Created ThreadPoolExecutor with %d workers",
                self.max_workers,
            )
        return self._executor

    def submit(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> TaskInfo:
        """Submit a task for background execution.

        Args:
            task_id: Unique identifier for this task.
            func: The function to execute (sync or async).
            args: Positional arguments to pass to the function.
            kwargs: Keyword arguments to pass to the function.
            on_progress: Optional callback for progress updates.

        Returns:
            TaskInfo with PENDING status.
        """
        now = time.time()

        info = TaskInfo(
            ref_id=task_id,
            status=TaskStatus.PENDING,
            started_at=now,
        )

        record = TaskRecord(
            info=info,
            on_progress=on_progress,
        )

        with self._lock:
            self._tasks[task_id] = record
            self._cleanup_if_needed()

        # Create wrapper that handles execution lifecycle
        def task_wrapper() -> Any:
            return self._execute_task(task_id, func, args, kwargs)

        # Submit to executor
        executor = self._get_executor()
        future = executor.submit(task_wrapper)

        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].future = future

        logger.info("Submitted task %s", task_id)

        return info

    def _execute_task(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """Execute a task in the background thread.

        Args:
            task_id: ID of the task being executed.
            func: The function to call.
            args: Positional arguments.
            kwargs: Keyword arguments.

        Returns:
            The result from the function.
        """
        # Check if cancelled before starting
        if task_id in self._cancelled:
            with self._lock:
                record = self._tasks.get(task_id)
                if record:
                    record.info.status = TaskStatus.CANCELLED
                    record.info.completed_at = time.time()
            logger.info("Task %s cancelled before start", task_id)
            return None

        # Mark as processing
        with self._lock:
            record = self._tasks.get(task_id)
            if record:
                record.info.status = TaskStatus.PROCESSING
                record.info.started_at = time.time()

        logger.info("Starting task %s", task_id)

        try:
            # Check if the function expects a progress callback
            # We inject it if the kwarg name matches
            if "progress_callback" in kwargs or self._func_accepts_progress(func):
                kwargs = {
                    **kwargs,
                    "progress_callback": self._make_progress_updater(task_id),
                }

            # Run async functions in a new event loop
            if asyncio.iscoroutinefunction(func):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(func(*args, **kwargs))
                finally:
                    loop.close()
            else:
                result = func(*args, **kwargs)

            # Check if cancelled during execution
            if task_id in self._cancelled:
                with self._lock:
                    record = self._tasks.get(task_id)
                    if record:
                        record.info.status = TaskStatus.CANCELLED
                        record.info.completed_at = time.time()
                logger.info("Task %s cancelled during execution", task_id)
                return None

            # Mark as complete
            with self._lock:
                record = self._tasks.get(task_id)
                if record:
                    record.info.status = TaskStatus.COMPLETE
                    record.info.completed_at = time.time()
                    record.result = result

            logger.info("Completed task %s", task_id)
            return result

        except Exception as exc:
            error_msg = str(exc)
            logger.error("Task %s failed: %s", task_id, error_msg)

            with self._lock:
                record = self._tasks.get(task_id)
                if record:
                    record.info.status = TaskStatus.FAILED
                    record.info.completed_at = time.time()
                    record.info.error = error_msg
                    record.exception = exc

            raise

    def _func_accepts_progress(self, func: Callable[..., Any]) -> bool:
        """Check if a function has a progress_callback parameter."""
        import inspect

        try:
            sig = inspect.signature(func)
            return "progress_callback" in sig.parameters
        except (ValueError, TypeError):
            return False

    def _make_progress_updater(
        self, task_id: str
    ) -> Callable[[int, int, str | None], bool]:
        """Create a progress update function for a task.

        Returns a callable that accepts (current, total, message) and
        returns False if the task has been cancelled.
        """

        def update_progress(
            current: int,
            total: int,
            message: str | None = None,
        ) -> bool:
            """Update task progress. Returns False if cancelled."""
            if task_id in self._cancelled:
                return False

            progress = TaskProgress(
                current=current,
                total=total,
                message=message,
            )

            with self._lock:
                record = self._tasks.get(task_id)
                if record:
                    record.info.progress = progress
                    # Call external progress callback if registered
                    if record.on_progress:
                        try:
                            record.on_progress(progress)
                        except Exception as exc:
                            logger.warning(
                                "Progress callback error for task %s: %s",
                                task_id,
                                exc,
                            )

            return True

        return update_progress

    def get_status(self, task_id: str) -> TaskInfo | None:
        """Get current status and progress of a task.

        Args:
            task_id: The task identifier.

        Returns:
            TaskInfo with current status, or None if task not found.
        """
        with self._lock:
            record = self._tasks.get(task_id)
            return record.info if record else None

    def get_result(self, task_id: str) -> Any:
        """Get the result of a completed task.

        Args:
            task_id: The task identifier.

        Returns:
            The return value from the executed function.

        Raises:
            KeyError: If task_id not found.
            RuntimeError: If task is not complete.
            Exception: Re-raises the original exception if task failed.
        """
        with self._lock:
            record = self._tasks.get(task_id)

            if record is None:
                raise KeyError(f"Task not found: {task_id}")

            if record.info.status == TaskStatus.FAILED:
                if record.exception:
                    raise record.exception
                raise RuntimeError(f"Task failed: {record.info.error}")

            if record.info.status != TaskStatus.COMPLETE:
                raise RuntimeError(
                    f"Task not complete: {task_id} (status={record.info.status.value})"
                )

            return record.result

    def cancel(self, task_id: str) -> bool:
        """Request cancellation of a task.

        Args:
            task_id: The task to cancel.

        Returns:
            True if cancellation was requested successfully,
            False if task not found or already in terminal state.
        """
        with self._lock:
            record = self._tasks.get(task_id)

            if record is None:
                return False

            if record.info.is_terminal:
                return False

            # Mark for cancellation
            self._cancelled.add(task_id)

            # If pending, cancel immediately
            if record.info.status == TaskStatus.PENDING:
                record.info.status = TaskStatus.CANCELLED
                record.info.completed_at = time.time()

                # Try to cancel the future
                if record.future and not record.future.done():
                    record.future.cancel()

                logger.info("Cancelled pending task %s", task_id)
                return True

            # If processing, just mark for cancellation
            # (task should check is_cancelled periodically)
            logger.info("Requested cancellation for running task %s", task_id)
            return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled.

        Args:
            task_id: The task to check.

        Returns:
            True if cancellation was requested for this task.
        """
        return task_id in self._cancelled

    def cleanup(self, max_age_seconds: float) -> int:
        """Remove old completed/failed/cancelled tasks.

        Args:
            max_age_seconds: Remove tasks completed more than this
                many seconds ago.

        Returns:
            Number of tasks removed.
        """
        now = time.time()
        cutoff = now - max_age_seconds

        with self._lock:
            to_remove = []
            for task_id, record in self._tasks.items():
                if (
                    record.info.is_terminal
                    and record.info.completed_at
                    and record.info.completed_at < cutoff
                ):
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]
                self._cancelled.discard(task_id)

        if to_remove:
            logger.info("Cleaned up %d old tasks", len(to_remove))

        return len(to_remove)

    def _cleanup_if_needed(self) -> None:
        """Remove oldest tasks if over the history limit.

        Must be called with self._lock held.
        """
        if len(self._tasks) <= self.max_task_history:
            return

        # Get terminal tasks sorted by completed_at
        terminal_tasks = [
            (task_id, record)
            for task_id, record in self._tasks.items()
            if record.info.is_terminal
        ]
        terminal_tasks.sort(
            key=lambda item: item[1].info.completed_at or 0,
        )

        # Remove oldest until under limit
        to_remove = len(self._tasks) - self.max_task_history
        for task_id, _ in terminal_tasks[:to_remove]:
            del self._tasks[task_id]
            self._cancelled.discard(task_id)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor and release resources.

        Args:
            wait: If True, wait for running tasks to complete.
                If False, attempt to cancel running tasks.
        """
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None
            logger.info("MemoryTaskBackend executor shutdown")

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the task backend.

        Returns:
            Dictionary with task counts by status and configuration.
        """
        with self._lock:
            status_counts: dict[str, int] = {}
            for record in self._tasks.values():
                status = record.info.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_tasks": len(self._tasks),
            "status_counts": status_counts,
            "max_workers": self.max_workers,
            "max_task_history": self.max_task_history,
            "executor_active": self._executor is not None,
            "cancelled_count": len(self._cancelled),
        }

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskInfo], int]:
        """List tasks with optional filtering.

        This is a convenience method not required by the protocol.

        Args:
            status: Filter by task status.
            limit: Maximum tasks to return.
            offset: Number of tasks to skip.

        Returns:
            Tuple of (task info list, total count).
        """
        with self._lock:
            tasks = [record.info for record in self._tasks.values()]

        # Apply filter
        if status:
            tasks = [task for task in tasks if task.status == status]

        # Sort by started_at descending (newest first)
        tasks.sort(key=lambda task: task.started_at, reverse=True)

        total = len(tasks)
        tasks = tasks[offset : offset + limit]

        return tasks, total
