# Task-04: Implement Polling Support in get_cached_result

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Modify `get_cached_result()` and `RefCache.get()` to return task status information when queried for a ref_id that corresponds to an in-flight async computation.

---

## Context
When a client receives a "processing" status from an async_timeout-enabled tool, they need a way to poll for completion. The existing `get_cached_result()` tool and `RefCache.get()` method need to be extended to:
1. Check if the ref_id corresponds to an active task
2. If yes → return task status with progress info
3. If task is complete → return normal cached result
4. If task failed → return error information with retry option

This enables the polling workflow: tool returns "processing" → client polls `get_cached_result(ref_id)` → eventually gets result or failure.

## Acceptance Criteria
- [ ] `RefCache.get()` checks `_active_tasks` before checking cache
- [ ] Returns `AsyncTaskResponse` for in-flight tasks
- [ ] Returns normal `CacheResponse` for completed tasks
- [ ] Returns error info for failed tasks (with `can_retry` flag)
- [ ] `get_cached_result` MCP tool handles both response types gracefully
- [ ] Progress information is included when available
- [ ] ETA calculation based on progress (if current/total available)
- [ ] Consistent response format for clients
- [ ] Unit tests for all polling scenarios

---

## Approach

### Modified get() Logic

```python
def get(
    self,
    ref_id: str,
    page: int = 1,
    page_size: int | None = None,
    actor: ActorLike = "agent",
    max_size: int | None = None,
) -> CacheResponse | AsyncTaskResponse:
    """Get a cached value or task status by reference ID.

    If the ref_id corresponds to an in-flight async task, returns
    AsyncTaskResponse with current status and progress.

    If the ref_id corresponds to a completed cache entry, returns
    CacheResponse with preview/value.
    """
    # Check active tasks first
    task_info = self.get_task_status(ref_id)
    if task_info is not None:
        if task_info.status == TaskStatus.COMPLETE:
            # Task complete - fall through to cache lookup
            pass
        elif task_info.status in (TaskStatus.PENDING, TaskStatus.PROCESSING):
            # Still processing - return task status
            return self._build_async_task_response(task_info)
        elif task_info.status == TaskStatus.FAILED:
            # Failed - return error with retry info
            return self._build_failed_task_response(task_info)

    # Normal cache lookup (existing logic)
    # ...
```

### New Helper Methods

```python
def _build_async_task_response(self, task_info: TaskInfo) -> AsyncTaskResponse:
    """Build response for an in-flight task."""
    eta = self._calculate_eta(task_info) if task_info.progress else None

    return AsyncTaskResponse(
        ref_id=task_info.ref_id,
        status=task_info.status,
        progress=task_info.progress,
        started_at=datetime.fromtimestamp(task_info.started_at).isoformat(),
        eta_seconds=eta,
        error=None,
        retry_count=task_info.retry_count,
        can_retry=task_info.retry_count < task_info.max_retries,
    )

def _calculate_eta(self, task_info: TaskInfo) -> float | None:
    """Estimate time remaining based on progress."""
    if task_info.progress is None:
        return None
    if task_info.progress.current is None or task_info.progress.total is None:
        return None
    if task_info.progress.current == 0:
        return None

    elapsed = time.time() - task_info.started_at
    rate = task_info.progress.current / elapsed
    remaining = task_info.progress.total - task_info.progress.current
    return remaining / rate if rate > 0 else None
```

### Files to Modify
1. `src/mcp_refcache/cache.py` - Modify `get()`, add helper methods
2. `tests/test_polling.py` - New test file for polling scenarios

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Design Considerations
- Return type changes from `CacheResponse` to `CacheResponse | AsyncTaskResponse`
- Need to update type hints and docstrings
- ETA calculation is best-effort, may be inaccurate for non-linear progress
- Consider caching ETA to avoid recalculating on every poll

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 models | ⚪ Pending | Need AsyncTaskResponse, TaskStatus |
| Task-02 task tracking | ⚪ Pending | Need get_task_status() method |
| Task-03 decorator | ⚪ Pending | Need working async_timeout to test |

---

## Commands & Snippets

```bash
# Run polling tests
uv run pytest tests/test_polling.py -v

# Run integration test with async timeout + polling
uv run pytest tests/test_async_timeout.py tests/test_polling.py -v
```

---

## Verification

```bash
# End-to-end polling test
uv run python -c "
import asyncio
import time
from mcp_refcache import RefCache

cache = RefCache()

@cache.cached(async_timeout=0.1)
async def slow_function():
    await asyncio.sleep(0.5)
    return {'data': 'result'}

async def test():
    # Start slow computation
    result = await slow_function()
    assert result['status'] == 'processing'
    ref_id = result['ref_id']

    # Poll until complete
    for _ in range(10):
        await asyncio.sleep(0.1)
        status = cache.get(ref_id)
        print(f'Status: {status}')
        if hasattr(status, 'value') or status.status == 'complete':
            print('Completed!')
            break
    else:
        print('Timeout waiting for completion')

asyncio.run(test())
"
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md)
- **Blocks:** [Task-05](../Task-05/scratchpad.md) (progress callbacks), [Task-06](../Task-06/scratchpad.md) (retry mechanism)
