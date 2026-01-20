"""Base types for task execution backends.

Defines the TaskBackend protocol that all async task execution
implementations must follow. Similar pattern to CacheBackend.
"""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from mcp_refcache.models import TaskInfo, TaskProgress

# Type alias for progress callback
ProgressCallback = Callable[[TaskProgress], None]


@runtime_checkable
class TaskBackend(Protocol):
    """Protocol defining the interface for async task execution backends.

    All task backends (memory, Hatchet, etc.) must implement this interface.
    The protocol uses duck typing - any class with these methods will work.

    Task backends are responsible for:
    - Submitting tasks for background execution
    - Tracking task status and progress
    - Storing results until retrieved
    - Supporting cancellation
    - Cleanup of old task records

    Example:
        ```python
        class MyTaskBackend:
            def submit(
                self,
                task_id: str,
                func: Callable[..., Any],
                args: tuple,
                kwargs: dict,
                on_progress: ProgressCallback | None = None,
            ) -> TaskInfo:
                # Implementation
                ...

            # ... implement other methods

        # Works because it has all required methods
        backend: TaskBackend = MyTaskBackend()
        ```
    """

    def submit(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> TaskInfo:
        """Submit a task for background execution.

        This method should return immediately after queuing the task.
        The actual execution happens in a background thread/process.

        Args:
            task_id: Unique identifier for this task.
            func: The function to execute (sync or async).
            args: Positional arguments to pass to the function.
            kwargs: Keyword arguments to pass to the function.
            on_progress: Optional callback for progress updates.
                The executing function can report progress by calling
                this callback with a TaskProgress object.

        Returns:
            TaskInfo with initial status (typically PENDING or PROCESSING).
        """
        ...

    def get_status(self, task_id: str) -> TaskInfo | None:
        """Get current status and progress of a task.

        Args:
            task_id: The task identifier.

        Returns:
            TaskInfo with current status, or None if task not found.
        """
        ...

    def get_result(self, task_id: str) -> Any:
        """Get the result of a completed task.

        This should only be called after verifying the task is complete
        via get_status(). Behavior for non-complete tasks is undefined.

        Args:
            task_id: The task identifier.

        Returns:
            The return value from the executed function.

        Raises:
            KeyError: If task_id not found.
            RuntimeError: If task is not complete.
            Exception: Re-raises the original exception if task failed.
        """
        ...

    def cancel(self, task_id: str) -> bool:
        """Request cancellation of a task.

        For running tasks, this sets a cancellation flag that the task
        should check periodically. For queued tasks, this may prevent
        execution entirely.

        Cancellation is cooperative - tasks must check for cancellation
        and exit gracefully.

        Args:
            task_id: The task to cancel.

        Returns:
            True if cancellation was requested successfully,
            False if task not found or already in terminal state.
        """
        ...

    def is_cancelled(self, task_id: str) -> bool:
        """Check if a task has been cancelled.

        Tasks should call this periodically during long operations
        to check if they should abort.

        Args:
            task_id: The task to check.

        Returns:
            True if cancellation was requested for this task.
        """
        ...

    def cleanup(self, max_age_seconds: float) -> int:
        """Remove old completed/failed/cancelled tasks.

        This should be called periodically to prevent memory leaks
        from accumulated task records.

        Args:
            max_age_seconds: Remove tasks completed more than this
                many seconds ago.

        Returns:
            Number of tasks removed.
        """
        ...

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the backend and release resources.

        Args:
            wait: If True, wait for running tasks to complete.
                If False, attempt to cancel running tasks.
        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the task backend.

        Returns:
            Dictionary with backend-specific statistics,
            typically including task counts by status.
        """
        ...
