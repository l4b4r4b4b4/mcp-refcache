"""Core Pydantic models for mcp-refcache.

Defines the data structures for cache references, responses,
configuration options, and async task tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SizeMode(str, Enum):
    """How to measure size for context limiting."""

    TOKEN = "token"  # Count tokens (accurate for LLM context)  # nosec B105
    CHARACTER = "character"  # Count characters (faster)


class PreviewStrategy(str, Enum):
    """Strategy for generating previews of large values."""

    TRUNCATE = "truncate"  # Stringify and cut at limit
    PAGINATE = "paginate"  # Split into pages, each respects limit
    SAMPLE = "sample"  # Pick evenly-spaced items, output respects limit


class AsyncResponseFormat(str, Enum):
    """Format options for async task responses.

    Controls how much detail is included when a task goes async
    and returns an in-flight response for polling.

    Can be configured at:
    - Decorator time: `@cache.cached(async_response_format="full")`
    - Call time: Pass `_async_response_format="full"` as parameter

    Call-time configuration overrides decorator-time configuration.
    """

    MINIMAL = "minimal"  # Just ref_id, status, is_async (for simple polling)
    STANDARD = "standard"  # Above + started_at, progress, message (default)
    FULL = "full"  # Above + expected_schema, eta_seconds, retry_info


class TaskStatus(str, Enum):
    """Status of an async computation.

    Used to track the lifecycle of background tasks spawned when
    a computation exceeds the async_timeout threshold.
    """

    PENDING = "pending"  # Task created but not yet started
    PROCESSING = "processing"  # Task is actively running
    COMPLETE = "complete"  # Task finished successfully
    FAILED = "failed"  # Task finished with an error
    CANCELLED = "cancelled"  # Task was cancelled by user


class TaskProgress(BaseModel):
    """Progress information for long-running tasks.

    Tools can report progress via the progress_callback protocol,
    enabling clients to display meaningful progress updates while polling.

    Example:
        ```python
        progress_callback(current=15, total=50, message="Indexing video 15/50")
        # Creates TaskProgress(current=15, total=50, percentage=30.0, message="...")
        ```
    """

    current: int | None = Field(
        default=None,
        ge=0,
        description="Current item/step number (0-indexed or 1-indexed by convention).",
    )
    total: int | None = Field(
        default=None,
        ge=0,
        description="Total items/steps expected for completion.",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable progress message for display.",
    )
    percentage: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Completion percentage (0-100). Auto-calculated if current/total provided.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Auto-calculate percentage if current and total are provided."""
        if (
            self.percentage is None
            and self.current is not None
            and self.total is not None
            and self.total > 0
        ):
            object.__setattr__(self, "percentage", (self.current / self.total) * 100.0)


class RetryInfo(BaseModel):
    """Information about a single retry attempt.

    Stored in TaskInfo.retry_history for debugging and analysis.
    """

    attempt: int = Field(
        ge=1,
        description="Retry attempt number (1-indexed).",
    )
    error: str = Field(
        description="Error message that triggered this retry.",
    )
    timestamp: float = Field(
        description="Unix timestamp when the retry was initiated.",
    )


class TaskInfo(BaseModel):
    """Internal tracking information for an async task.

    This model stores the complete state of a background task, including
    status, progress, timing, error information, and retry history.
    Not returned directly to clients - use AsyncTaskResponse for API responses.

    Example:
        ```python
        task_info = TaskInfo(
            ref_id="default:abc123",
            status=TaskStatus.PROCESSING,
            started_at=time.time(),
            progress=TaskProgress(current=5, total=50),
        )
        ```
    """

    ref_id: str = Field(
        description="Reference ID for the cached result (once complete).",
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current task status.",
    )
    progress: TaskProgress | None = Field(
        default=None,
        description="Progress information if reported by the task.",
    )
    started_at: float = Field(
        description="Unix timestamp when the task started.",
    )
    completed_at: float | None = Field(
        default=None,
        description="Unix timestamp when the task completed (success, failure, or cancel).",
    )
    error: str | None = Field(
        default=None,
        description="Error message if task failed.",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts made so far.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts allowed for this task.",
    )
    retry_history: list[RetryInfo] = Field(
        default_factory=list,
        description="History of all retry attempts with errors and timestamps.",
    )

    @property
    def can_retry(self) -> bool:
        """Check if the task can be retried.

        Returns True if the task has failed and hasn't exhausted retries.
        """
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries

    @property
    def is_terminal(self) -> bool:
        """Check if the task is in a terminal state.

        Terminal states are: COMPLETE, FAILED (with exhausted retries), CANCELLED.
        """
        if self.status in (TaskStatus.COMPLETE, TaskStatus.CANCELLED):
            return True
        return self.status == TaskStatus.FAILED and not self.can_retry

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time since task started."""
        import time

        end_time = self.completed_at if self.completed_at else time.time()
        return end_time - self.started_at


class ExpectedSchema(BaseModel):
    """Schema information for the expected result of an async task.

    Provides type hints and structure preview so agents know what
    to expect when the task completes.
    """

    return_type: str | None = Field(
        default=None,
        description="String representation of the return type annotation.",
    )
    fields: dict[str, str] | None = Field(
        default=None,
        description="Field names and their types (for dict/Pydantic returns).",
    )
    example: Any | None = Field(
        default=None,
        description="Example/default structure of the expected result.",
    )
    description: str | None = Field(
        default=None,
        description="Description of what the result contains.",
    )


class AsyncTaskResponse(BaseModel):
    """Response format for in-flight async computations.

    Returned when polling for a task that hasn't completed yet.
    Provides status, progress, timing, and retry information.

    The detail level is controlled by AsyncResponseFormat:
    - MINIMAL: ref_id, status, is_async only
    - STANDARD: Above + started_at, progress, message
    - FULL: Above + expected_schema, eta_seconds, retry_info

    Example:
        ```python
        # Polling response for a processing task
        response = AsyncTaskResponse(
            ref_id="default:abc123",
            status=TaskStatus.PROCESSING,
            progress=TaskProgress(current=15, total=50),
            started_at="2025-01-15T12:00:00Z",
            eta_seconds=45.0,
        )
        ```
    """

    ref_id: str = Field(
        description="Reference ID for polling and eventual result retrieval.",
    )
    status: TaskStatus = Field(
        description="Current task status.",
    )
    progress: TaskProgress | None = Field(
        default=None,
        description="Progress information if available.",
    )
    started_at: str = Field(
        description="ISO 8601 timestamp when the task started.",
    )
    eta_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description="Estimated seconds until completion (based on progress rate).",
    )
    error: str | None = Field(
        default=None,
        description="Error message if status is FAILED.",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts made so far.",
    )
    can_retry: bool = Field(
        default=True,
        description="Whether the task can be retried (if failed).",
    )
    message: str | None = Field(
        default=None,
        description="Human-readable status message for the client.",
    )
    expected_schema: ExpectedSchema | None = Field(
        default=None,
        description="Schema of expected result (included in FULL format).",
    )

    @classmethod
    def from_task_info(
        cls,
        task_info: TaskInfo,
        eta_seconds: float | None = None,
        message: str | None = None,
        expected_schema: ExpectedSchema | None = None,
        response_format: "AsyncResponseFormat" = AsyncResponseFormat.STANDARD,
    ) -> "AsyncTaskResponse":
        """Create an AsyncTaskResponse from internal TaskInfo.

        Args:
            task_info: Internal task tracking information.
            eta_seconds: Optional ETA override (calculated externally).
            message: Optional human-readable message.
            expected_schema: Schema of expected result (for FULL format).
            response_format: Detail level for the response.

        Returns:
            AsyncTaskResponse suitable for returning to clients.
        """
        started_at_iso = datetime.fromtimestamp(
            task_info.started_at, tz=timezone.utc
        ).isoformat()

        # Generate default message based on status
        if message is None:
            if task_info.status == TaskStatus.PROCESSING:
                if task_info.progress and task_info.progress.message:
                    message = task_info.progress.message
                else:
                    message = f"Task is processing (ref_id={task_info.ref_id})"
            elif task_info.status == TaskStatus.PENDING:
                message = "Task is queued and will start shortly"
            elif task_info.status == TaskStatus.FAILED:
                message = f"Task failed: {task_info.error}"
            elif task_info.status == TaskStatus.CANCELLED:
                message = "Task was cancelled"
            elif task_info.status == TaskStatus.COMPLETE:
                message = "Task completed successfully"

        # Build response based on format level
        if response_format == AsyncResponseFormat.MINIMAL:
            return cls(
                ref_id=task_info.ref_id,
                status=task_info.status,
                started_at=started_at_iso,
            )
        elif response_format == AsyncResponseFormat.STANDARD:
            return cls(
                ref_id=task_info.ref_id,
                status=task_info.status,
                progress=task_info.progress,
                started_at=started_at_iso,
                eta_seconds=eta_seconds,
                error=task_info.error,
                retry_count=task_info.retry_count,
                can_retry=task_info.can_retry,
                message=message,
            )
        else:  # FULL
            return cls(
                ref_id=task_info.ref_id,
                status=task_info.status,
                progress=task_info.progress,
                started_at=started_at_iso,
                eta_seconds=eta_seconds,
                error=task_info.error,
                retry_count=task_info.retry_count,
                can_retry=task_info.can_retry,
                message=message,
                expected_schema=expected_schema,
            )

    def to_dict(
        self,
        response_format: "AsyncResponseFormat" = AsyncResponseFormat.STANDARD,
    ) -> dict[str, Any]:
        """Convert to dictionary with format-appropriate fields.

        Args:
            response_format: Detail level for the response.

        Returns:
            Dictionary suitable for returning from cached decorator.
        """
        base = {
            "ref_id": self.ref_id,
            "status": self.status.value,
            "is_complete": False,
            "is_async": True,
        }

        if response_format == AsyncResponseFormat.MINIMAL:
            return base

        # STANDARD adds these fields
        base["started_at"] = self.started_at
        base["progress"] = self.progress.model_dump() if self.progress else None
        base["message"] = self.message

        if response_format == AsyncResponseFormat.STANDARD:
            return base

        # FULL adds these fields
        base["eta_seconds"] = self.eta_seconds
        base["error"] = self.error
        base["retry_count"] = self.retry_count
        base["can_retry"] = self.can_retry
        base["expected_schema"] = (
            self.expected_schema.model_dump() if self.expected_schema else None
        )

        return base


class PreviewConfig(BaseModel):
    """Configuration for context limiting behavior."""

    size_mode: SizeMode = Field(
        default=SizeMode.TOKEN,
        description="How to measure size (tokens or characters).",
    )
    max_size: int = Field(
        default=1000,
        description="Maximum size in tokens or characters.",
        gt=0,
    )
    default_strategy: PreviewStrategy = Field(
        default=PreviewStrategy.SAMPLE,
        description="Default strategy for generating previews.",
    )


class CacheReference(BaseModel):
    """Reference to a cached value.

    This is what gets returned to agents instead of the full value.
    The agent can use this reference to:
    - Paginate through the data
    - Pass to another tool (server resolves it)
    - Request the full value (if permitted)
    """

    ref_id: str = Field(
        description="Unique identifier for this cached value.",
    )
    cache_name: str = Field(
        description="Name of the cache containing this value.",
    )
    namespace: str = Field(
        default="public",
        description="Namespace for isolation and access control.",
    )
    tool_name: str | None = Field(
        default=None,
        description="Name of the tool that created this reference.",
    )
    created_at: float = Field(
        description="Unix timestamp when the reference was created.",
    )
    expires_at: float | None = Field(
        default=None,
        description="Unix timestamp when the reference expires (None = never).",
    )

    # Metadata about the cached value
    total_items: int | None = Field(
        default=None,
        description="Total number of items if value is a collection.",
    )
    total_size: int | None = Field(
        default=None,
        description="Total size in bytes of the cached value.",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Estimated token count of the full value.",
    )


class PaginatedResponse(BaseModel):
    """Response containing a page of data with navigation info."""

    items: list[Any] = Field(
        description="Items in the current page.",
    )
    page: int = Field(
        description="Current page number (1-indexed).",
        ge=1,
    )
    page_size: int = Field(
        description="Number of items per page.",
        ge=1,
    )
    total_items: int = Field(
        description="Total number of items across all pages.",
        ge=0,
    )
    total_pages: int = Field(
        description="Total number of pages.",
        ge=0,
    )
    has_next: bool = Field(
        description="Whether there are more pages after this one.",
    )
    has_previous: bool = Field(
        description="Whether there are pages before this one.",
    )

    @classmethod
    def from_list(
        cls,
        items: list[Any],
        page: int = 1,
        page_size: int = 20,
    ) -> "PaginatedResponse":
        """Create a paginated response from a list."""
        total_items = len(items)
        total_pages = (
            (total_items + page_size - 1) // page_size if total_items > 0 else 0
        )
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = items[start_idx:end_idx]

        return cls(
            items=page_items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )


class CacheResponse(BaseModel):
    """Standard response format for cached values.

    Combines reference metadata with preview/value data.
    This is what MCP tools should return for large responses.
    """

    # Reference info (always present)
    ref_id: str = Field(
        description="Reference ID for accessing the cached value.",
    )
    cache_name: str = Field(
        description="Name of the cache containing this value.",
    )
    namespace: str = Field(
        default="public",
        description="Namespace for isolation.",
    )

    # Metadata about the full value
    total_items: int | None = Field(
        default=None,
        description="Total number of items if value is a collection.",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Estimated token count of the full value.",
    )

    # Size metadata from PreviewResult
    original_size: int | None = Field(
        default=None,
        description="Size of the original value (in tokens or characters).",
    )
    preview_size: int | None = Field(
        default=None,
        description="Size of the preview (in tokens or characters).",
    )

    # The preview (structured, not stringified!)
    preview: Any = Field(
        description="Preview of the value (structured data, respects size limit).",
    )
    preview_strategy: PreviewStrategy = Field(
        description="Strategy used to generate the preview.",
    )

    # Pagination info (if applicable)
    page: int | None = Field(
        default=None,
        description="Current page number (if paginated).",
    )
    total_pages: int | None = Field(
        default=None,
        description="Total pages available (if paginated).",
    )

    # What can the agent do next?
    available_actions: list[str] = Field(
        default_factory=lambda: ["get_page", "resolve_full", "pass_to_tool"],
        description="Actions available to the agent.",
    )
