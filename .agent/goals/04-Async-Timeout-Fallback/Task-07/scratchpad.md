# Task-07: Add Cancellation API

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement a cancellation mechanism that allows clients to cancel in-flight async tasks, freeing resources and stopping unnecessary background computations.

---

## Context
When a client starts a long-running computation but no longer needs the result (e.g., user navigates away, request superseded), they should be able to cancel the task. This:
- Frees memory and CPU resources
- Prevents unnecessary work
- Allows graceful cleanup of partial state

Without cancellation, background tasks would run to completion even when results are unwanted.

## Acceptance Criteria
- [ ] `cancel_task(ref_id: str)` method added to RefCache
- [ ] Returns `True` if task was cancelled, `False` if not found or already complete
- [ ] Cancelled tasks have status `CANCELLED` (new enum value)
- [ ] Background asyncio.Task is actually cancelled (not just marked)
- [ ] `CancelledError` is caught and handled gracefully
- [ ] Partial results are cleaned up (no orphaned cache entries)
- [ ] `cancel_task` MCP tool exposed for client use (optional)
- [ ] Cancellation is idempotent (cancelling twice is safe)
- [ ] Unit tests for cancellation scenarios
- [ ] Documentation updated

---

## Approach

### New Status Enum Value

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"  # NEW
```

### New Methods

```python
async def cancel_task(self, ref_id: str) -> bool:
    """Cancel an in-flight async task.

    Args:
        ref_id: Reference ID of the task to cancel

    Returns:
        True if task was cancelled, False if not found or already terminal
    """
    async with self._task_lock:
        task_info = self._active_tasks.get(ref_id)
        if task_info is None:
            return False

        if task_info.status in (TaskStatus.COMPLETE, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False  # Already terminal

        # Cancel the actual asyncio task
        if hasattr(task_info, '_task') and not task_info._task.done():
            task_info._task.cancel()

        # Update status
        task_info.status = TaskStatus.CANCELLED
        task_info.completed_at = time.time()

        return True

def is_cancellable(self, ref_id: str) -> bool:
    """Check if a task can be cancelled."""
    task_info = self.get_task_status(ref_id)
    if task_info is None:
        return False
    return task_info.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
```

### Background Task Cancellation Handling

```python
async def background_computation():
    try:
        result = await func(*resolved_args, **resolved_kwargs)
        ref = self.set(cache_key, result, ...)
        await self.complete_task(ref_id)
    except asyncio.CancelledError:
        # Task was cancelled - update status is already done by cancel_task
        # Clean up any partial state if needed
        raise  # Re-raise to properly terminate
    except Exception as e:
        await self.fail_task(ref_id, str(e))
        raise
```

### Optional MCP Tool

```python
@mcp.tool
async def cancel_async_task(ref_id: str) -> dict:
    """Cancel an in-flight async computation.

    Args:
        ref_id: Reference ID of the task to cancel

    Returns:
        Dictionary with cancellation status and message
    """
    cancelled = await cache.cancel_task(ref_id)
    if cancelled:
        return {"success": True, "message": f"Task {ref_id} cancelled"}
    else:
        return {"success": False, "message": f"Task {ref_id} not found or already complete"}
```

### Files to Modify
1. `src/mcp_refcache/models.py` - Add CANCELLED to TaskStatus
2. `src/mcp_refcache/cache.py` - Add cancel_task, is_cancellable methods
3. `tests/test_cancellation.py` - New test file

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Design Considerations
- Store reference to asyncio.Task in TaskInfo for actual cancellation
- Use `task.cancel()` which raises `CancelledError` in the task
- Cancellation should be immediate, not wait for task to acknowledge
- Consider timeout for cleanup operations after cancellation
- Cancelled tasks should be cleaned up by the periodic cleanup task

### Edge Cases
- Cancelling a task that's about to complete (race condition)
- Cancelling a task during retry attempt
- Double cancellation (should be idempotent)
- Cancelling a non-existent ref_id

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-01 models | ⚪ Pending | Need TaskStatus enum |
| Task-02 task tracking | ⚪ Pending | Need _active_tasks dict |
| Task-03 async_timeout | ⚪ Pending | Need background task creation |
| Task-04 polling | ⚪ Pending | Need to show CANCELLED status in polling |

---

## Commands & Snippets

```bash
# Run cancellation tests
uv run pytest tests/test_cancellation.py -v

# Test with real async delays
uv run pytest tests/test_cancellation.py -v --timeout=30
```

---

## Verification

```bash
# Integration test with cancellation
uv run python -c "
import asyncio
from mcp_refcache import RefCache, TaskStatus

cache = RefCache()

@cache.cached(async_timeout=0.1)
async def slow_function():
    await asyncio.sleep(10.0)  # Very slow
    return {'data': 'result'}

async def test():
    # Start slow computation
    result = await slow_function()
    assert result['status'] == 'processing'
    ref_id = result['ref_id']
    print(f'Started task: {ref_id}')

    # Cancel it
    cancelled = await cache.cancel_task(ref_id)
    print(f'Cancelled: {cancelled}')
    assert cancelled is True

    # Check status
    status = cache.get_task_status(ref_id)
    print(f'Status: {status.status if status else None}')
    assert status.status == TaskStatus.CANCELLED

    # Double cancel should be safe
    cancelled_again = await cache.cancel_task(ref_id)
    assert cancelled_again is False

    print('Cancellation API working!')

asyncio.run(test())
"
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-01](../Task-01/scratchpad.md), [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md), [Task-04](../Task-04/scratchpad.md)
- **Related Tasks:** [Task-06](../Task-06/scratchpad.md) (retry - cancelled tasks might be retryable)
