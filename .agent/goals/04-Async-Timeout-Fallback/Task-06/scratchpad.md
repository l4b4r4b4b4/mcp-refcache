# Task-06: Implement Retry Mechanism for Failed Tasks

## Status
- [x] Not Started
- [ ] In Progress
- [ ] Blocked
- [ ] Complete

## Objective
Implement a configurable retry mechanism for failed async tasks, allowing automatic or manual retries with exponential backoff and sensible defaults.

---

## Context
When async tasks fail (network errors, transient failures, etc.), users should be able to retry them without re-calling the original tool. The retry mechanism should:
- Support automatic retries with configurable limits
- Use exponential backoff to avoid hammering failing services
- Allow manual retry via API call
- Track retry attempts and history

This makes long-running operations more robust in the face of transient failures.

## Acceptance Criteria
- [ ] `max_retries: int = 3` parameter added to `cached()` decorator
- [ ] `retry_delay: float = 1.0` base delay parameter (for exponential backoff)
- [ ] `retry_backoff_factor: float = 2.0` parameter for exponential scaling
- [ ] Automatic retry on failure (up to max_retries)
- [ ] `retry_task(ref_id)` method for manual retry
- [ ] Retry attempts tracked in `TaskInfo.retry_count`
- [ ] Backoff delay: `retry_delay * (retry_backoff_factor ** retry_count)`
- [ ] `can_retry` flag in responses indicates if retry is possible
- [ ] Failed tasks with exhausted retries marked as permanently failed
- [ ] Unit tests for retry scenarios (success on retry, exhausted retries, manual retry)

---

## Approach

### Decorator Parameters

```python
def cached(
    self,
    # ... existing params ...
    async_timeout: float | None = None,
    progress_enabled: bool = False,
    # NEW RETRY PARAMETERS
    max_retries: int = 3,
    retry_delay: float = 1.0,
    retry_backoff_factor: float = 2.0,
):
```

### Retry Logic in Background Task

```python
async def background_computation():
    retry_count = 0
    last_error = None

    while retry_count <= max_retries:
        try:
            result = await func(*resolved_args, **resolved_kwargs)
            ref = self.set(cache_key, result, ...)
            await self.complete_task(ref_id)
            return
        except Exception as e:
            last_error = e
            retry_count += 1
            await self.update_task_retry(ref_id, retry_count, str(e))

            if retry_count <= max_retries:
                delay = retry_delay * (retry_backoff_factor ** (retry_count - 1))
                await asyncio.sleep(delay)
            else:
                await self.fail_task(ref_id, str(e), exhausted=True)
                raise
```

### Manual Retry Method

```python
async def retry_task(self, ref_id: str) -> AsyncTaskResponse:
    """Manually retry a failed task.

    Args:
        ref_id: Reference ID of the failed task

    Returns:
        AsyncTaskResponse with new status

    Raises:
        ValueError: If task doesn't exist or can't be retried
    """
    task_info = self.get_task_status(ref_id)
    if task_info is None:
        raise ValueError(f"No task found for ref_id: {ref_id}")

    if task_info.status != TaskStatus.FAILED:
        raise ValueError(f"Can only retry failed tasks, status is: {task_info.status}")

    if not task_info.can_retry:
        raise ValueError("Task has exhausted all retry attempts")

    # Reset and re-execute
    # ... implementation ...
```

### TaskInfo Extensions

```python
class TaskInfo(BaseModel):
    # ... existing fields ...
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    last_error: str | None = Field(default=None)
    retry_history: list[dict] = Field(default_factory=list)  # [{attempt, error, timestamp}]

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries and self.status == TaskStatus.FAILED
```

### Files to Modify
1. `src/mcp_refcache/models.py` - Extend TaskInfo with retry fields
2. `src/mcp_refcache/cache.py` - Add retry params to decorator, retry_task method
3. `tests/test_retry.py` - New test file for retry scenarios

---

## Notes & Discoveries

### Session Log
| Date | Summary |
|------|---------|
| 2025-01-15 | Initial task creation |

### Design Considerations
- Exponential backoff: 1s, 2s, 4s, 8s... (with factor=2)
- Cap maximum delay at some reasonable value (e.g., 60s)?
- Consider jitter to avoid thundering herd
- Store retry history for debugging
- Manual retry resets the retry counter? Or continues from current count?

### Default Values Rationale
- `max_retries=3`: Standard practice, covers most transient failures
- `retry_delay=1.0`: Start with 1 second, reasonable for network ops
- `retry_backoff_factor=2.0`: Standard exponential backoff

---

## Blockers & Dependencies

| Blocker/Dependency | Status | Resolution |
|--------------------|--------|------------|
| Task-02 task tracking | ⚪ Pending | Need task info storage |
| Task-03 async_timeout | ⚪ Pending | Need background task execution |
| Task-04 polling | ⚪ Pending | Need status reporting for retries |

---

## Commands & Snippets

```bash
# Run retry tests
uv run pytest tests/test_retry.py -v

# Run with coverage
uv run pytest tests/test_retry.py --cov=mcp_refcache.cache --cov-report=term-missing
```

---

## Verification

```bash
# Test automatic retry on transient failure
uv run python -c "
import asyncio
from mcp_refcache import RefCache

cache = RefCache()
attempt_count = 0

@cache.cached(async_timeout=0.1, max_retries=3)
async def flaky_function():
    global attempt_count
    attempt_count += 1
    if attempt_count < 3:
        raise ValueError(f'Transient error on attempt {attempt_count}')
    return {'success': True, 'attempts': attempt_count}

async def test():
    result = await flaky_function()
    print(f'Initial result: {result}')

    # Wait for retries to complete
    await asyncio.sleep(5)

    status = cache.get(result['ref_id'])
    print(f'Final status: {status}')

asyncio.run(test())
"
```

---

## Related
- **Parent Goal:** [04-Async-Timeout-Fallback](../scratchpad.md)
- **Depends On:** [Task-02](../Task-02/scratchpad.md), [Task-03](../Task-03/scratchpad.md), [Task-04](../Task-04/scratchpad.md)
- **Related Tasks:** None
