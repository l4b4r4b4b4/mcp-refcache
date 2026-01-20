"""Tests for async task models.

Tests for TaskStatus, TaskProgress, TaskInfo, RetryInfo, and AsyncTaskResponse models
used in the async timeout fallback feature.
"""

import time

import pytest
from pydantic import ValidationError

from mcp_refcache import (
    AsyncTaskResponse,
    RetryInfo,
    TaskInfo,
    TaskProgress,
    TaskStatus,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_status_values_exist(self) -> None:
        """Verify all expected status values are defined."""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.PROCESSING == "processing"
        assert TaskStatus.COMPLETE == "complete"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"

    def test_status_is_string_enum(self) -> None:
        """TaskStatus values should be usable as strings."""
        assert TaskStatus.PROCESSING == "processing"
        assert TaskStatus.COMPLETE.value == "complete"

    def test_status_from_string(self) -> None:
        """Can create TaskStatus from string value."""
        assert TaskStatus("pending") == TaskStatus.PENDING
        assert TaskStatus("processing") == TaskStatus.PROCESSING

    def test_invalid_status_raises(self) -> None:
        """Invalid status string should raise ValueError."""
        with pytest.raises(
            ValueError, match="'invalid_status' is not a valid TaskStatus"
        ):
            TaskStatus("invalid_status")


class TestTaskProgress:
    """Tests for TaskProgress model."""

    def test_empty_progress(self) -> None:
        """Progress can be created with no fields."""
        progress = TaskProgress()
        assert progress.current is None
        assert progress.total is None
        assert progress.message is None
        assert progress.percentage is None

    def test_progress_with_current_and_total(self) -> None:
        """Progress with current/total auto-calculates percentage."""
        progress = TaskProgress(current=25, total=100)
        assert progress.current == 25
        assert progress.total == 100
        assert progress.percentage == 25.0

    def test_progress_percentage_calculation(self) -> None:
        """Percentage is calculated correctly for various values."""
        # 50%
        progress = TaskProgress(current=50, total=100)
        assert progress.percentage == 50.0

        # Fractional percentage
        progress = TaskProgress(current=1, total=3)
        assert progress.percentage == pytest.approx(33.333, rel=0.01)

        # 0%
        progress = TaskProgress(current=0, total=100)
        assert progress.percentage == 0.0

        # 100%
        progress = TaskProgress(current=100, total=100)
        assert progress.percentage == 100.0

    def test_progress_with_explicit_percentage(self) -> None:
        """Explicit percentage is not overwritten."""
        progress = TaskProgress(current=25, total=100, percentage=50.0)
        # Explicit percentage should be preserved
        assert progress.percentage == 50.0

    def test_progress_with_message(self) -> None:
        """Progress can include a message."""
        progress = TaskProgress(current=5, total=50, message="Indexing video 5/50")
        assert progress.message == "Indexing video 5/50"

    def test_progress_zero_total_no_percentage(self) -> None:
        """Zero total should not calculate percentage (avoid division by zero)."""
        progress = TaskProgress(current=0, total=0)
        assert progress.percentage is None

    def test_progress_validation_negative_current(self) -> None:
        """Negative current value should fail validation."""
        with pytest.raises(ValidationError):
            TaskProgress(current=-1, total=100)

    def test_progress_validation_percentage_over_100(self) -> None:
        """Percentage over 100 should fail validation."""
        with pytest.raises(ValidationError):
            TaskProgress(percentage=101.0)

    def test_progress_validation_negative_percentage(self) -> None:
        """Negative percentage should fail validation."""
        with pytest.raises(ValidationError):
            TaskProgress(percentage=-5.0)

    def test_progress_serialization(self) -> None:
        """Progress can be serialized to dict."""
        progress = TaskProgress(current=10, total=50, message="Working...")
        data = progress.model_dump()
        assert data["current"] == 10
        assert data["total"] == 50
        assert data["message"] == "Working..."
        assert data["percentage"] == 20.0


class TestRetryInfo:
    """Tests for RetryInfo model."""

    def test_retry_info_creation(self) -> None:
        """RetryInfo can be created with required fields."""
        timestamp = time.time()
        retry = RetryInfo(attempt=1, error="Connection timeout", timestamp=timestamp)
        assert retry.attempt == 1
        assert retry.error == "Connection timeout"
        assert retry.timestamp == timestamp

    def test_retry_info_attempt_must_be_positive(self) -> None:
        """Attempt number must be >= 1."""
        with pytest.raises(ValidationError):
            RetryInfo(attempt=0, error="Error", timestamp=time.time())

    def test_retry_info_serialization(self) -> None:
        """RetryInfo can be serialized and deserialized."""
        timestamp = 1705312800.0
        retry = RetryInfo(attempt=2, error="Network error", timestamp=timestamp)
        data = retry.model_dump()
        assert data["attempt"] == 2
        assert data["error"] == "Network error"
        assert data["timestamp"] == timestamp

        # Deserialize
        retry2 = RetryInfo.model_validate(data)
        assert retry2.attempt == 2
        assert retry2.error == "Network error"


class TestTaskInfo:
    """Tests for TaskInfo model."""

    def test_task_info_minimal(self) -> None:
        """TaskInfo can be created with minimal required fields."""
        task = TaskInfo(ref_id="default:abc123", started_at=time.time())
        assert task.ref_id == "default:abc123"
        assert task.status == TaskStatus.PENDING
        assert task.progress is None
        assert task.error is None
        assert task.retry_count == 0
        assert task.max_retries == 3
        assert task.retry_history == []

    def test_task_info_with_progress(self) -> None:
        """TaskInfo can include progress information."""
        progress = TaskProgress(current=5, total=50)
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.PROCESSING,
            progress=progress,
        )
        assert task.progress is not None
        assert task.progress.current == 5
        assert task.progress.percentage == 10.0

    def test_task_info_can_retry_when_failed(self) -> None:
        """can_retry is True for failed tasks with retries remaining."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.FAILED,
            error="Connection error",
            retry_count=0,
            max_retries=3,
        )
        assert task.can_retry is True

    def test_task_info_cannot_retry_when_exhausted(self) -> None:
        """can_retry is False when retries are exhausted."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.FAILED,
            error="Connection error",
            retry_count=3,
            max_retries=3,
        )
        assert task.can_retry is False

    def test_task_info_cannot_retry_when_complete(self) -> None:
        """can_retry is False for completed tasks."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.COMPLETE,
            retry_count=0,
        )
        assert task.can_retry is False

    def test_task_info_cannot_retry_when_cancelled(self) -> None:
        """can_retry is False for cancelled tasks."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.CANCELLED,
            retry_count=0,
        )
        assert task.can_retry is False

    def test_task_info_is_terminal_complete(self) -> None:
        """is_terminal is True for completed tasks."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.COMPLETE,
        )
        assert task.is_terminal is True

    def test_task_info_is_terminal_cancelled(self) -> None:
        """is_terminal is True for cancelled tasks."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.CANCELLED,
        )
        assert task.is_terminal is True

    def test_task_info_is_terminal_failed_exhausted(self) -> None:
        """is_terminal is True for failed tasks with exhausted retries."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        assert task.is_terminal is True

    def test_task_info_not_terminal_failed_can_retry(self) -> None:
        """is_terminal is False for failed tasks that can retry."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )
        assert task.is_terminal is False

    def test_task_info_not_terminal_processing(self) -> None:
        """is_terminal is False for processing tasks."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=time.time(),
            status=TaskStatus.PROCESSING,
        )
        assert task.is_terminal is False

    def test_task_info_elapsed_seconds_processing(self) -> None:
        """elapsed_seconds calculates time since start for processing tasks."""
        started = time.time() - 5.0  # Started 5 seconds ago
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=started,
            status=TaskStatus.PROCESSING,
        )
        # Should be approximately 5 seconds (allow some tolerance)
        assert 4.9 <= task.elapsed_seconds <= 5.5

    def test_task_info_elapsed_seconds_completed(self) -> None:
        """elapsed_seconds uses completed_at for finished tasks."""
        started = 1000.0
        completed = 1010.0  # 10 seconds later
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=started,
            completed_at=completed,
            status=TaskStatus.COMPLETE,
        )
        assert task.elapsed_seconds == 10.0

    def test_task_info_with_retry_history(self) -> None:
        """TaskInfo can store retry history."""
        history = [
            RetryInfo(attempt=1, error="Timeout", timestamp=1000.0),
            RetryInfo(attempt=2, error="Connection refused", timestamp=1005.0),
        ]
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1000.0,
            status=TaskStatus.PROCESSING,
            retry_count=2,
            retry_history=history,
        )
        assert len(task.retry_history) == 2
        assert task.retry_history[0].error == "Timeout"
        assert task.retry_history[1].attempt == 2

    def test_task_info_serialization(self) -> None:
        """TaskInfo can be serialized and deserialized."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705312800.0,
            status=TaskStatus.PROCESSING,
            progress=TaskProgress(current=25, total=100),
        )
        data = task.model_dump()
        assert data["ref_id"] == "default:abc123"
        assert data["status"] == "processing"
        assert data["progress"]["percentage"] == 25.0

        # Deserialize
        task2 = TaskInfo.model_validate(data)
        assert task2.ref_id == "default:abc123"
        assert task2.status == TaskStatus.PROCESSING


class TestAsyncTaskResponse:
    """Tests for AsyncTaskResponse model."""

    def test_async_response_minimal(self) -> None:
        """AsyncTaskResponse can be created with required fields."""
        response = AsyncTaskResponse(
            ref_id="default:abc123",
            status=TaskStatus.PROCESSING,
            started_at="2025-01-15T12:00:00Z",
        )
        assert response.ref_id == "default:abc123"
        assert response.status == TaskStatus.PROCESSING
        assert response.started_at == "2025-01-15T12:00:00Z"
        assert response.progress is None
        assert response.eta_seconds is None
        assert response.error is None
        assert response.retry_count == 0
        assert response.can_retry is True

    def test_async_response_with_progress(self) -> None:
        """AsyncTaskResponse can include progress."""
        response = AsyncTaskResponse(
            ref_id="default:abc123",
            status=TaskStatus.PROCESSING,
            started_at="2025-01-15T12:00:00Z",
            progress=TaskProgress(current=25, total=100, message="Working..."),
            eta_seconds=45.0,
        )
        assert response.progress is not None
        assert response.progress.current == 25
        assert response.eta_seconds == 45.0

    def test_async_response_failed_with_error(self) -> None:
        """AsyncTaskResponse for failed task includes error."""
        response = AsyncTaskResponse(
            ref_id="default:abc123",
            status=TaskStatus.FAILED,
            started_at="2025-01-15T12:00:00Z",
            error="Connection timeout after 30s",
            retry_count=2,
            can_retry=True,
        )
        assert response.status == TaskStatus.FAILED
        assert response.error == "Connection timeout after 30s"
        assert response.retry_count == 2
        assert response.can_retry is True

    def test_async_response_from_task_info_processing(self) -> None:
        """from_task_info creates correct response for processing task."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1736942400.0,  # 2025-01-15T12:00:00Z
            status=TaskStatus.PROCESSING,
            progress=TaskProgress(current=10, total=50),
        )
        response = AsyncTaskResponse.from_task_info(task, eta_seconds=40.0)

        assert response.ref_id == "default:abc123"
        assert response.status == TaskStatus.PROCESSING
        assert response.started_at == "2025-01-15T12:00:00+00:00"
        assert response.progress is not None
        assert response.progress.current == 10
        assert response.eta_seconds == 40.0
        assert response.message == "Task is processing (ref_id=default:abc123)"

    def test_async_response_from_task_info_failed(self) -> None:
        """from_task_info creates correct response for failed task."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705320000.0,
            status=TaskStatus.FAILED,
            error="Network error",
            retry_count=1,
            max_retries=3,
        )
        response = AsyncTaskResponse.from_task_info(task)

        assert response.status == TaskStatus.FAILED
        assert response.error == "Network error"
        assert response.retry_count == 1
        assert response.can_retry is True
        assert "Task failed: Network error" in (response.message or "")

    def test_async_response_from_task_info_with_progress_message(self) -> None:
        """from_task_info uses progress message when available."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705320000.0,
            status=TaskStatus.PROCESSING,
            progress=TaskProgress(current=5, total=10, message="Indexing video 5/10"),
        )
        response = AsyncTaskResponse.from_task_info(task)

        assert response.message == "Indexing video 5/10"

    def test_async_response_from_task_info_custom_message(self) -> None:
        """from_task_info allows custom message override."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705320000.0,
            status=TaskStatus.PROCESSING,
        )
        response = AsyncTaskResponse.from_task_info(
            task, message="Custom progress update"
        )

        assert response.message == "Custom progress update"

    def test_async_response_from_task_info_pending(self) -> None:
        """from_task_info handles pending status."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705320000.0,
            status=TaskStatus.PENDING,
        )
        response = AsyncTaskResponse.from_task_info(task)

        assert response.status == TaskStatus.PENDING
        assert "queued" in (response.message or "").lower()

    def test_async_response_from_task_info_cancelled(self) -> None:
        """from_task_info handles cancelled status."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705320000.0,
            status=TaskStatus.CANCELLED,
        )
        response = AsyncTaskResponse.from_task_info(task)

        assert response.status == TaskStatus.CANCELLED
        assert "cancelled" in (response.message or "").lower()

    def test_async_response_from_task_info_complete(self) -> None:
        """from_task_info handles complete status."""
        task = TaskInfo(
            ref_id="default:abc123",
            started_at=1705320000.0,
            status=TaskStatus.COMPLETE,
            completed_at=1705320060.0,
        )
        response = AsyncTaskResponse.from_task_info(task)

        assert response.status == TaskStatus.COMPLETE
        assert "completed" in (response.message or "").lower()

    def test_async_response_serialization(self) -> None:
        """AsyncTaskResponse can be serialized to dict."""
        response = AsyncTaskResponse(
            ref_id="default:abc123",
            status=TaskStatus.PROCESSING,
            started_at="2025-01-15T12:00:00Z",
            progress=TaskProgress(current=50, total=100),
            eta_seconds=30.0,
            message="Halfway done",
        )
        data = response.model_dump()

        assert data["ref_id"] == "default:abc123"
        assert data["status"] == "processing"
        assert data["progress"]["percentage"] == 50.0
        assert data["eta_seconds"] == 30.0
        assert data["message"] == "Halfway done"

    def test_async_response_validation_negative_eta(self) -> None:
        """Negative ETA should fail validation."""
        with pytest.raises(ValidationError):
            AsyncTaskResponse(
                ref_id="default:abc123",
                status=TaskStatus.PROCESSING,
                started_at="2025-01-15T12:00:00Z",
                eta_seconds=-10.0,
            )

    def test_async_response_validation_negative_retry_count(self) -> None:
        """Negative retry count should fail validation."""
        with pytest.raises(ValidationError):
            AsyncTaskResponse(
                ref_id="default:abc123",
                status=TaskStatus.PROCESSING,
                started_at="2025-01-15T12:00:00Z",
                retry_count=-1,
            )
