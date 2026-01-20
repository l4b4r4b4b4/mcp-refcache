"""Tests for async timeout functionality and polling.

Tests cover:
- Async timeout triggering background execution
- Polling with RefCache.get() returning AsyncTaskResponse
- Task completion and result retrieval
- ETA calculation based on progress
- Task cleanup after completion
- Multiple concurrent async tasks
- Timeout with sync functions
- Error handling in background tasks
"""

import asyncio
import time
from typing import Any

import pytest

from mcp_refcache import RefCache
from mcp_refcache.backends.task_memory import MemoryTaskBackend
from mcp_refcache.models import AsyncTaskResponse, CacheResponse, TaskStatus


class TestAsyncTimeout:
    """Test async timeout behavior with background execution."""

    @pytest.mark.asyncio
    async def test_async_function_exceeds_timeout_returns_processing_status(
        self,
    ) -> None:
        """Async function exceeding timeout returns processing status immediately."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()

        # Should return immediately with processing status
        assert result["status"] == "processing"
        assert result["is_async"] is True
        assert result["is_complete"] is False
        assert "ref_id" in result
        assert "started_at" in result

    @pytest.mark.asyncio
    async def test_async_function_within_timeout_returns_result(self) -> None:
        """Async function completing within timeout returns result directly."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=1.0)
        async def fast_task() -> dict[str, int]:
            await asyncio.sleep(0.05)
            return {"result": 42}

        result = await fast_task()

        # Should return completed result (is_complete=True, value present)
        assert result["is_complete"] is True
        assert result["is_async"] is False
        assert result["value"] == {"result": 42}

    @pytest.mark.asyncio
    async def test_sync_function_exceeds_timeout_returns_processing_status(
        self,
    ) -> None:
        """Sync function exceeding timeout returns processing status immediately."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        def slow_sync_task() -> dict[str, int]:
            time.sleep(0.5)
            return {"result": 42}

        result = slow_sync_task()

        # Should return immediately with processing status
        assert result["status"] == "processing"
        assert result["is_async"] is True
        assert result["is_complete"] is False
        assert "ref_id" in result

    @pytest.mark.asyncio
    async def test_background_task_completes_and_caches_result(self) -> None:
        """Background task completes and result is cached."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.3)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Wait for background task to complete
        await asyncio.sleep(0.5)

        # Result should be cached now
        cached_result = cache.resolve(ref_id)
        assert cached_result == {"result": 42}

    @pytest.mark.asyncio
    async def test_multiple_concurrent_async_tasks(self) -> None:
        """Multiple async tasks can run concurrently."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=3))

        @cache.cached(async_timeout=0.1)
        async def task(n: int) -> dict[str, int]:
            await asyncio.sleep(0.3)
            return {"result": n * 2}

        # Start multiple tasks
        result1 = await task(1)
        result2 = await task(2)
        result3 = await task(3)

        # All should return processing status
        assert result1["status"] == "processing"
        assert result2["status"] == "processing"
        assert result3["status"] == "processing"

        # Wait for completion
        await asyncio.sleep(0.5)

        # All should be cached
        assert cache.resolve(result1["ref_id"]) == {"result": 2}
        assert cache.resolve(result2["ref_id"]) == {"result": 4}
        assert cache.resolve(result3["ref_id"]) == {"result": 6}

    @pytest.mark.asyncio
    async def test_async_timeout_with_cache_hit_returns_immediately(self) -> None:
        """Cached result returns immediately even with async_timeout set."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        # First call - will timeout
        result1 = await task()
        assert result1["status"] == "processing"

        # Wait for completion
        await asyncio.sleep(0.7)

        # Second call - should return cached result immediately
        result2 = await task()
        assert result2["is_complete"] is True
        assert result2["value"] == {"result": 42}


class TestPolling:
    """Test polling for task status with RefCache.get()."""

    @pytest.mark.asyncio
    async def test_get_returns_async_task_response_for_in_flight_task(self) -> None:
        """RefCache.get() returns AsyncTaskResponse for in-flight tasks."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Poll immediately - should get AsyncTaskResponse
        response = cache.get(ref_id)
        assert isinstance(response, AsyncTaskResponse)
        assert response.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
        assert response.ref_id == ref_id

    @pytest.mark.asyncio
    async def test_get_returns_cache_response_for_completed_task(self) -> None:
        """RefCache.get() returns CacheResponse once task completes."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.3)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        # Poll - should get CacheResponse
        response = cache.get(ref_id)
        assert isinstance(response, CacheResponse)
        assert response.preview == {"result": 42}

    @pytest.mark.asyncio
    async def test_polling_workflow_from_processing_to_complete(self) -> None:
        """Polling workflow: processing → complete."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.4)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Initial poll - should be processing
        response1 = cache.get(ref_id)
        assert isinstance(response1, AsyncTaskResponse)
        assert response1.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)

        # Wait for completion
        await asyncio.sleep(0.5)

        # Final poll - should be complete
        response2 = cache.get(ref_id)
        assert isinstance(response2, CacheResponse)
        assert response2.preview == {"result": 42}

    @pytest.mark.asyncio
    async def test_get_task_status_returns_none_for_nonexistent_task(self) -> None:
        """get_task_status() returns None for non-existent task."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        status = cache.get_task_status("nonexistent:ref123")
        assert status is None

    @pytest.mark.asyncio
    async def test_get_task_status_returns_task_info_for_active_task(self) -> None:
        """get_task_status() returns TaskInfo for active task."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Get status
        status = cache.get_task_status(ref_id)
        assert status is not None
        assert status.ref_id == ref_id
        assert status.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)


class TestETACalculation:
    """Test ETA calculation based on progress."""

    @pytest.mark.asyncio
    async def test_eta_is_none_when_no_progress(self) -> None:
        """ETA is None when task has no progress information."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Poll - should have no ETA without progress
        response = cache.get(ref_id)
        assert isinstance(response, AsyncTaskResponse)
        assert response.eta_seconds is None

    @pytest.mark.asyncio
    async def test_calculate_eta_returns_none_for_zero_progress(self) -> None:
        """_calculate_eta returns None when current progress is 0."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        from mcp_refcache.models import TaskInfo, TaskProgress

        task_info = TaskInfo(
            ref_id="test:123",
            status=TaskStatus.PROCESSING,
            started_at=time.time(),
            progress=TaskProgress(current=0, total=100),
        )

        eta = cache._calculate_eta(task_info)
        assert eta is None


class TestTaskCleanup:
    """Test task cleanup after completion."""

    @pytest.mark.asyncio
    async def test_completed_task_removed_from_active_tasks(self) -> None:
        """Completed tasks are removed from _active_tasks on next get()."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.3)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Task should be in _active_tasks
        assert ref_id in cache._active_tasks

        # Wait for completion
        await asyncio.sleep(0.5)

        # Call get() which should clean up
        response = cache.get(ref_id)
        assert isinstance(response, CacheResponse)

        # Task should be removed from _active_tasks
        assert ref_id not in cache._active_tasks

    @pytest.mark.asyncio
    async def test_multiple_calls_to_get_after_completion(self) -> None:
        """Multiple get() calls after completion all return CacheResponse."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.3)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        # Multiple calls should all return CacheResponse
        response1 = cache.get(ref_id)
        response2 = cache.get(ref_id)
        response3 = cache.get(ref_id)

        assert isinstance(response1, CacheResponse)
        assert isinstance(response2, CacheResponse)
        assert isinstance(response3, CacheResponse)


class TestErrorHandling:
    """Test error handling in background tasks."""

    @pytest.mark.asyncio
    async def test_background_task_exception_updates_task_status(self) -> None:
        """Background task exception updates task status to FAILED."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def failing_task() -> dict[str, int]:
            await asyncio.sleep(0.2)
            raise ValueError("Task failed!")

        result = await failing_task()
        ref_id = result["ref_id"]

        # Wait for task to fail
        await asyncio.sleep(0.4)

        # Poll - should show failed status
        response = cache.get(ref_id)
        assert isinstance(response, AsyncTaskResponse)
        assert response.status == TaskStatus.FAILED
        assert "Task failed!" in (response.error or "")

    @pytest.mark.asyncio
    async def test_failed_task_does_not_cache_result(self) -> None:
        """Failed tasks do not cache a result."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def failing_task() -> dict[str, int]:
            await asyncio.sleep(0.2)
            raise ValueError("Task failed!")

        result = await failing_task()
        ref_id = result["ref_id"]

        # Wait for task to fail
        await asyncio.sleep(0.4)

        # Should not be able to resolve (raises KeyError)
        with pytest.raises(KeyError):
            cache.resolve(ref_id)


class TestAsyncResponseFormat:
    """Test async response format levels."""

    @pytest.mark.asyncio
    async def test_minimal_format_returns_minimal_fields(self) -> None:
        """Minimal format returns only essential fields."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1, async_response_format="minimal")
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()

        # Should have minimal fields
        assert "ref_id" in result
        assert "status" in result
        assert "is_async" in result
        # Should NOT have detailed fields
        assert "progress" not in result or result["progress"] is None
        assert "eta_seconds" not in result

    @pytest.mark.asyncio
    async def test_standard_format_returns_standard_fields(self) -> None:
        """Standard format returns standard fields."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1, async_response_format="standard")
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()

        # Should have standard fields
        assert "ref_id" in result
        assert "status" in result
        assert "started_at" in result
        assert "message" in result

    @pytest.mark.asyncio
    async def test_full_format_returns_all_fields(self) -> None:
        """Full format returns all fields including schema."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1, async_response_format="full")
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.5)
            return {"result": 42}

        result = await slow_task()

        # Should have all fields
        assert "ref_id" in result
        assert "status" in result
        assert "started_at" in result
        assert "message" in result
        # Full format includes retry info
        assert "can_retry" in result or "retry_count" in result


class TestConcurrentAccess:
    """Test concurrent access to async tasks."""

    @pytest.mark.asyncio
    async def test_polling_from_multiple_coroutines(self) -> None:
        """Multiple coroutines can poll the same task concurrently."""
        cache = RefCache(name="test", task_backend=MemoryTaskBackend(max_workers=2))

        @cache.cached(async_timeout=0.1)
        async def slow_task() -> dict[str, int]:
            await asyncio.sleep(0.4)
            return {"result": 42}

        result = await slow_task()
        ref_id = result["ref_id"]

        async def poll_task() -> Any:
            """Poll the task until complete."""
            for _ in range(10):
                response = cache.get(ref_id)
                if isinstance(response, CacheResponse):
                    return response.preview
                await asyncio.sleep(0.1)
            return None

        # Poll from multiple coroutines
        results = await asyncio.gather(poll_task(), poll_task(), poll_task())

        # All should get the same result
        assert all(r == {"result": 42} for r in results)
